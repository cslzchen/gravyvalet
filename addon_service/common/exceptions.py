class AddonServiceException(Exception):
    pass  # TODO: unique error codes; translatable names/descriptions


class ExpiredAccessToken(AddonServiceException):
    pass


class ItemNotFound(AddonServiceException):
    pass


class UnexpectedAddonError(AddonServiceException):
    pass
