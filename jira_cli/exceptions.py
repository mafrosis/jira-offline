'''
A module for custom application exceptions.
'''
class EpicNotFound(Exception):
    pass


class EstimateFieldUnavailable(Exception):
    pass


class SummaryAlreadyExists(Exception):
    pass


class DeserializeError(ValueError):
    pass
