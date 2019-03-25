import pytest
import run as grp


class MockFinder(object):
    def __init__(self, container_type, count=1):
        self.container_type = container_type
        self.count = count

    def find(self, filter=None):
        for i in range(self.count):
            yield MockParent(self.container_type)


class MockParent(object):
    def __init__(self, container_type):
        self.container_type = container_type
        if container_type == 'project':
            self.subjects = MockFinder('subject')
        if container_type in ['project', 'subject']:
            self.sessions = MockFinder('session')
        if container_type == 'session':
            self.acquisitions = MockFinder('acquisition')
        self.id = '{}_id'.format(container_type)
        self.label = '{}_label'.format(container_type)


def test_find_all_for_project():
    project = MockParent('project')
    expected_value = [
        {
            '_id': 'subject_id',
            'label': 'subject_label',
            'type': 'subject'
        },
        {
            '_id': 'session_id',
            'label': 'session_label',
            'type': 'session'
        },
        {
            '_id': 'acquisition_id',
            'label': 'acquisition_label',
            'type': 'acquisition'
        }
    ]

    assert expected_value == grp.find_error_containers('all', project)


def test_find_subject_project():
    project = MockParent('project')
    expected_value = [
        {
            '_id': 'subject_id',
            'label': 'subject_label',
            'type': 'subject'
        }
    ]

    assert expected_value == grp.find_error_containers('subject', project)


def test_find_session_project():
    project = MockParent('project')
    expected_value = [
        {
            '_id': 'session_id',
            'label': 'session_label',
            'type': 'session'
        }
    ]

    assert expected_value == grp.find_error_containers('session', project)


def test_find_acquisition_project():
    project = MockParent('project')
    expected_value = [
        {
            '_id': 'acquisition_id',
            'label': 'acquisition_label',
            'type': 'acquisition'
        }
    ]
    actual_value = grp.find_error_containers('acquisition', project)
    print(actual_value)
    assert expected_value == actual_value
