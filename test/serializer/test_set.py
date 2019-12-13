from dataclasses import dataclass

from jira_cli.main import DataclassSerializer


@dataclass
class Test(DataclassSerializer):
    s: set


def test_set_deserialize():
    """
    Test set deserializes
    """
    obj = Test.deserialize({'s': [1, 2, 3]})
    assert isinstance(obj.s, set)
    assert obj.s == {1, 2, 3}

def test_set_deserialize_rounsrip():
    """
    Test set deserializes/serializes in a loss-less rounsrip
    """
    json = Test.deserialize({'s': [1, 2, 3]}).serialize()
    assert json['s'] == [1, 2, 3]

def test_set_serialize():
    """
    Test set serializes
    """
    json = Test(s={1, 2, 3}).serialize()
    assert json['s'] == [1, 2, 3]

def test_set_serialize_rounsrip():
    """
    Test set serializes/deserializes in a loss-less rounsrip
    """
    obj = Test.deserialize(
        Test(s={1, 2, 3}).serialize()
    )
    assert obj.s == {1, 2, 3}
