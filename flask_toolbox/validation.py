import re

import marshmallow
from marshmallow import ValidationError
from marshmallow import fields
from marshmallow import post_dump
from marshmallow import validates_schema

from flask_toolbox import toolbox_proxy


class Skip(fields.Field):
    ERROR_MSG = 'Skip must be 0 or positive integer.'

    def __init__(self, default=0, **kwargs):
        # "missing" is used on deserialize
        super(Skip, self).__init__(default=default, missing=default, **kwargs)

    def _deserialize(self, val, attr, obj):
        try:
            val = int(val)
        except ValueError:
            raise ValidationError(self.ERROR_MSG)
        return super(Skip, self)._deserialize(val, attr, obj)

    def _serialize(self, val, attr, obj):
        try:
            val = int(val)
        except ValueError:
            raise ValidationError(self.ERROR_MSG)
        return super(Skip, self)._serialize(val, attr, obj)

    def _validate(self, val):
        if val < 0:
            raise ValidationError(self.ERROR_MSG)
        return super(Skip, self)._validate(val)


class USE_APPLICATION_DEFAULT(object):
    pass


class Limit(fields.Field):
    ERROR_MSG = 'Limit must be a positive integer.'

    def __init__(self, default=USE_APPLICATION_DEFAULT, **kwargs):
        super(Limit, self).__init__(missing=default, **kwargs)

    def _deserialize(self, val, attr, obj):
        if isinstance(val, USE_APPLICATION_DEFAULT):
            val = toolbox_proxy.pagination_limit_max
        try:
            val = int(val)
        except ValueError:
            raise ValidationError(self.ERROR_MSG)
        return super(Limit, self)._deserialize(val, attr, obj)

    def _serialize(self, val, attr, obj):
        try:
            val = int(val)
        except ValueError:
            raise ValidationError(self.ERROR_MSG)
        return super(Limit, self)._serialize(val, attr, obj)

    def _validate(self, val):
        if val <= 0:
            raise ValidationError(self.ERROR_MSG)
        limit_max = toolbox_proxy.pagination_limit_max
        if val > limit_max:
            raise ValidationError('Maximum limit is {}'.format(limit_max))
        return super(Limit, self)._validate(val)


class ObjectId(fields.Str):
    ERROR_MSG = "Not a valid ObjectID."

    def _deserialize(self, val, attr, data):
        if not _is_oid(val):
            raise ValidationError(self.ERROR_MSG)

        return super(ObjectId, self)._deserialize(val, attr, data)

    def _serialize(self, val, attr, obj):
        if not _is_oid(val):
            raise ValidationError(self.ERROR_MSG)

        return super(ObjectId, self)._serialize(val, attr, obj)


class UUID(fields.Str):
    ERROR_MSG = "Not a valid UUID."

    def _deserialize(self, val, attr, data):
        if not _is_uuid(val):
            raise ValidationError(self.ERROR_MSG)

        return super(UUID, self)._deserialize(val, attr, data)

    def _serialize(self, val, attr, obj):
        if not _is_uuid(val):
            raise ValidationError(self.ERROR_MSG)

        return super(UUID, self)._serialize(val, attr, obj)


REGEX_OID = re.compile('[0-9a-fA-F]{24}$')
def _is_oid(value):
    return REGEX_OID.match(value) is not None


REGEX_UUID = re.compile('[0-9A-Fa-f]{8}-([0-9A-Fa-f]{4}-){3}[0-9A-Fa-f]{12}$')
def _is_uuid(value):
    return REGEX_UUID.match(value) is not None


class CommaSeparatedList(fields.List):
    def _deserialize(self, value, attr, data):
        items = value.split(',')
        return super(CommaSeparatedList, self)._deserialize(items, attr, data)

    def _serialize(self, value, attr, obj):
        items = super(CommaSeparatedList, self)._serialize(value, attr, obj)
        return ','.join([str(i) for i in items])


class ActuallyRequireOnDumpMixin(object):
    @post_dump()
    def require_output_fields(self, data):
        for field_name in self.fields:
            field = self.fields[field_name]
            if field.required:
                if field_name not in data:
                    raise ValidationError("Required field missing: {}".format(field_name))
                elif field.allow_none is False and data[field_name] is None:
                    raise ValidationError("Value for required field cannot be None: {}".format(field_name))


class DisallowExtraFieldsMixin(object):
    @validates_schema(pass_original=True)
    def disallow_extra_fields(self, processed_data, original_data):
        input_fields = original_data.keys()
        expected_fields = list(self.fields) + [
            field.load_from
            for field in self.fields.values()
            if field.load_from is not None
        ]
        excluded_fields = self.exclude
        unsupported_fields = set(input_fields) - set(expected_fields) - set(excluded_fields)
        if len(unsupported_fields) > 0:
            raise ValidationError(message='Unexpected field: {}'.format(','.join(unsupported_fields)))


def add_custom_error_message(base_class, field_validation_error_function):
    """
    Creates a Marshmallow field class that returns a custom
    validation error message.

    :param marshmallow.fields.Field base_class:
      Marshmallow field class
    :param field_validation_error_function:
      A function that takes one value argument and returns a string
    :return: A new Marshmallow field class
    """
    class CustomErrorMessageClass(base_class):
        def _deserialize(self, value, attr, data):
            try:
                return super(CustomErrorMessageClass, self)._deserialize(value, attr, data)
            except ValidationError:
                raise ValidationError(field_validation_error_function(value))

        def _validate(self, value):
            try:
                super(CustomErrorMessageClass, self)._validate(value)
            except ValidationError:
                raise ValidationError(field_validation_error_function(value))
    return CustomErrorMessageClass


class RequestSchema(marshmallow.Schema, DisallowExtraFieldsMixin):
    pass


class ResponseSchema(marshmallow.Schema, ActuallyRequireOnDumpMixin):
    pass