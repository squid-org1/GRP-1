#!/usr/bin/env python

import csv
import datetime
import flywheel
import json
import logging


CSV_HEADERS = [
    '_id',
    'label',
    'type',
    'resolved'
]

log = logging.getLogger('grp-2')


def collect_containers(finder, container_type, collect_acquisitions=False,
                       skip_sessions=False):
    """Iterates over finder for containers with tags=error filter, and returns
    a list of dictionaries with the container id, label, and type

    Args:
        finder (Finder): A flywheel sdk finder
        container_type (str): The container type returned by the finder
        collect_acquisitions (bool): Optional flag to iterate over the
            acquisitions
        skip_sessions (bool): Optional flag to skip collecting sessions if only
            collecting acquisitions

    Returns:
        list: A list of dictionaries with the container id, label, and type set
    """
    error_containers = []
    for container in finder.find('tags=error'):
        if container_type != 'session' or not skip_sessions:
            error_containers.append({
                '_id': container.id,
                'label': container.label,
                'type': container_type
            })
        if collect_acquisitions:
            for acquisition in container.acquisitions.find('tags=error'):
                error_containers.append({
                    '_id': acquisition.id,
                    'label': acquisition.label,
                    'type': 'acquisition'
                })
    return error_containers


def find_error_containers(container_type, parent):
    """Given a parent and a container type, the function will return a list
    of all containers of the given container_type that have the tag error

    Args:
        container_type (str): Must be 'all', 'subject', 'session', or
            'acquisition'
        parent (ContainerOutput): The parent container, can be a project,
            subject, or session, and this restrict what the container type can
            be

    Returns:
        list: A list of containers (_id, label, and type) that are tagged as
            error
    """
    error_containers = []
    if container_type not in ['all', 'subject', 'session', 'acquisition']:
        raise ValueError('Container type {} not valid'.format(container_type))

    # If collecting all container types under the project or just subjects
    if (
        ( container_type == 'all' and parent.container_type == 'project')  or
        ( container_type == 'subject')
    ):
        if parent.container_type != 'project':
            # If the parent type isn't a project, the user selected subject as
            # as the container_type but didn't run the job on a project
            raise ValueError('Cannot find subjects of a parent of type %s',
                             parent.container_type)

        error_containers += collect_containers(parent.subjects, 'subject')

    # If collecting all container types under a project or a subject; or just
    # the sessions under a container, or acquisitions
    # NOTE: This is because we have to loop through the sessions to get through
    # all acquisitions of a project or subject
    if (
        ( container_type == 'all' and parent.container_type in ['project', 'subject'])  or
        ( container_type in ['session', 'acquisition'])
    ):
        if parent.container_type not in ['project', 'subject'] and container_type == 'session':
            # If the parent type isn't a container above a session, but session
            # was specifically chosen as container type raise and exception
            raise ValueError('Cannot find sessions of a parent of type %s',
                             parent.container_type)

        collect_acquisitions = container_type == 'all' or container_type == 'acquisition'
        skip_sessions = container_type == 'acquisition'
        error_containers += collect_containers(parent.sessions, 'session',
                                               collect_acquisitions=collect_acquisitions,
                                               skip_sessions=skip_sessions)

    # If the parent type is a session, loop through the acquisitions
    if parent.container_type == 'session':
        if container_type not in ['all', 'acquisition']:
            # User should not choose a session to run if container_type is not
            # all or acquisition
            raise ValueError('Invalid container type {} for children of session'.format(container_type))
        error_containers += collect_containers(parent.acquisitions, 'acquisition')

    return error_containers


def create_output_file(container_type, error_containers, file_type,
                       gear_context, output_filename=None):
    """Creates the output file from a set of error containers, the file type
    is determined from the config value

    Args:
        containers (str): The container type to describe in the output file
        error_containers (list): list of containers that were tagged
        file_type (str): The file type to format the output into
        gear_context (GearContext): the gear context so that we can write out
            the file
        output_filename (str): and optional file name that can be passed

    Returns:
        str: The filename that was used to write the report as
    """
    file_ext = 'csv' if file_type == 'csv' else 'json'
    output_filename = output_filename or 'error-report-{}-{}.{}'.format(
        container_type,
        datetime.datetime.utcnow(),
        file_ext
    )
    with gear_context.open_output(output_filename, 'w') as output_file:
        if file_type == 'json':
            json.dump(error_containers, output_file)
        elif file_type == 'csv':
            csv_dict_writer = csv.DictWriter(output_file,
                                             fieldnames=CSV_HEADERS)
            csv_dict_writer.writeheader()
            for container in error_containers:
                csv_dict_writer.writerow(container)
        else:
            raise Exception('CRITICAL: {} is not a valid file type')
    return output_filename


def set_resolved_status(error_containers, client, validator):
    """Sets the resolved boolean on the container dictionary in error the
    containers

    Args:
        error_containers (list): list of container dictionaries
        client (Client): An api client
        validator (function): A function that return true or false given a
            container
    """
    for container_dictionary in error_containers:
        container = client.get_container(container_dictionary['_id'])
        resolved = validator(container)
        if resolved and container.get_file('error.log'):
            log.info('Deleting error.log for {}={}...'.format(
                container.container_type,
                container.id
            ))
            container.delete_file('error.log')
            container.delete_tag('error')
        container_dictionary['resolved'] = resolved

def main():
    with flywheel.GearContext() as gear_context:
        gear_context.init_logging()
        log.info(gear_context.config)
        log.info(gear_context.destination)
        container_type = gear_context.config.get('container_type')
        parent = gear_context.client.get_container(
            gear_context.destination['id']
        )

        # Get all containers
        # TODO: Should it be based on whether the error.log file exists?
        log.debug('Finding containers with errors...')
        error_containers = find_error_containers(container_type, parent)

        # Set the status for the containers
        log.info('Resolving status for invalid containers...')
        # TODO: Figure out the validator stuff, maybe have our validation be a
        # pip module?
        set_resolved_status(error_containers, gear_context.client,
                            lambda x: True)

        log.info('Writing error report')
        filename = create_output_file(container_type, error_containers,
                                      gear_context.config.get('file_type'),
                                      gear_context,
                                      gear_context.config.get('filename'))
        log.info('Wrote error report with filename {}'.format(filename))


if __name__ == '__main__':
    main()
