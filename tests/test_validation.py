import uuid
from datetime import datetime
from unittest import TestCase

import flask_testing
from flask import Flask
from marshmallow import Schema
from marshmallow import ValidationError
from marshmallow import fields

from flask_toolbox import Toolbox
from flask_toolbox.validation import ActuallyRequireOnDumpMixin
from flask_toolbox.validation import CommaSeparatedList
from flask_toolbox.validation import DisallowExtraFieldsMixin
from flask_toolbox.validation import Limit
from flask_toolbox.validation import ObjectId
from flask_toolbox.validation import Skip
from flask_toolbox.validation import UUID
from flask_toolbox.validation import add_custom_error_message


def error_msg_function(some_value):
    return 'A wild {} appeared'.format(some_value)


class ErrorWrappingTestSchema(Schema, DisallowExtraFieldsMixin):
    a = add_custom_error_message(
        base_class=fields.Integer,
        field_validation_error_function=error_msg_function)(allow_none=True)


class DisallowExtraFieldsSchema(Schema, DisallowExtraFieldsMixin):
    a = fields.String()
    b = fields.String(load_from='c')


class TestDisallowExtraFieldsMixin(TestCase):

    def test_nominal(self):
        _, errors = DisallowExtraFieldsSchema(strict=True).dump({})
        self.assertEqual(errors, {})

    def test_unexpected_field(self):
        data, errs = DisallowExtraFieldsSchema().load({'foo': 'bar'})
        self.assertEqual(errs, {'_schema': ['Unexpected field: foo']})

    def test_respects_load_from_and_attribute(self):
        data, errors = DisallowExtraFieldsSchema().load({'c': 'bar'})
        self.assertEqual({}, errors)
        self.assertEqual(data, {'b': 'bar'})

    def test_respects_exclude(self):
        schema = DisallowExtraFieldsSchema(exclude=('a',))
        data, errors = schema.load({'a': 'yz'})
        self.assertEqual(errors, {})
        self.assertEqual(data, {})


class ActuallyRequireOnDumpMixinSchema(Schema, ActuallyRequireOnDumpMixin):
    optional = fields.Str()
    value_optional = fields.Str(required=True, allow_none=True)
    value_required = fields.Str(required=True, allow_none=False)
    validation_required = fields.DateTime(required=True, allow_none=False)


class RequireOutpuMixinTest(TestCase):

    def setUp(self):
        super(RequireOutpuMixinTest, self).setUp()
        self.schema = ActuallyRequireOnDumpMixinSchema(strict=True)
        self.data = {
            'value_required': 'abc',
            'value_optional': None,
            'validation_required': datetime.now(),
        }

    def test_nominal(self):
        self.schema.dump(self.data)

    def test_required_missing(self):
        del self.data['value_required']
        with self.assertRaises(ValidationError) as ctx:
            self.schema.dump(self.data)
        self.assertIn('value_required', ctx.exception.messages['_schema'][0])

    def test_required_none(self):
        self.data['value_required'] = None
        with self.assertRaises(ValidationError) as ctx:
            self.schema.dump(self.data)
        self.assertIn('value_required', ctx.exception.messages['_schema'][0])

    def test_value_optional_missing(self):
        del self.data['value_optional']
        with self.assertRaises(ValidationError) as ctx:
            self.schema.dump(self.data)
        self.assertIn('value_optional', ctx.exception.messages['_schema'][0])

    def test_validation_works(self):
        self.data['validation_required'] = '123'
        with self.assertRaises(ValidationError) as ctx:
            self.schema.dump(self.data)
        # it's some sort of date error
        self.assertIn('cannot be formatted as a datetime',
                      ctx.exception.messages['validation_required'][0])



class TestErrorWrappingClass(TestCase):
    def test_wrap_on_load(self):
        wrong_input = 'a string'

        encoded_data, errors = ErrorWrappingTestSchema().load({'a': wrong_input})
        self.assertEqual(1, len(errors))
        self.assertEqual(error_msg_function(wrong_input), errors['a'][0])

    def test_wrap_on_validate(self):
        wrong_input = 'a string'

        errors = ErrorWrappingTestSchema().validate({'a': wrong_input})
        self.assertEqual(1, len(errors))
        self.assertEqual(error_msg_function(wrong_input), errors['a'][0])

    def test_does_not_wrap_on_dump(self):
        wrong_input = 'a string'
        encoded_data, errors = ErrorWrappingTestSchema().dump({'a': wrong_input})

        # The Marshmallow Integer class raises an exception that isn't wrapped
        self.assertEqual(1, len(errors))
        self.assertNotEqual(error_msg_function(wrong_input), errors['a'][0])


class StringList(Schema):
    foos = CommaSeparatedList(fields.String())


class IntegerList(Schema):
    foos = CommaSeparatedList(fields.Integer())


class TestCommaSeparatedList(TestCase):
    def test_deserialize(self):
        data, _ = StringList().load({'foos': 'bar'})
        self.assertEqual(data['foos'], ['bar'])

        data, _ = StringList().load({'foos': 'bar,baz'})
        self.assertEqual(data['foos'], ['bar', 'baz'])

        data, _ = IntegerList().load({'foos': '1,2'})
        self.assertEqual(data['foos'], [1, 2])

    def test_serialize(self):
        data, _ = StringList().dump({'foos': ['bar']})
        self.assertEqual(data['foos'], 'bar')

        data, _ = StringList().dump({'foos': ['bar', 'baz']})
        self.assertEqual(data['foos'], 'bar,baz')

        data, _ = IntegerList().dump({'foos': [1, 2]})
        self.assertEqual(data['foos'], '1,2')

    def test_deserialize_errors(self):
        _, errs = IntegerList().load({'foos': '1,two'})
        self.assertEqual(errs, {
            'foos': {1: ['Not a valid integer.']}
        })

    def test_serialize_errors(self):
        _, errs = IntegerList().dump({'foos': [1, 'two']})
        self.assertEqual(errs, {
            # Marshmallow's fields.List formats the dump errors differently
            # than load :shrug:
            'foos': ['Not a valid integer.']
        })


class ObjectWithUUID(Schema):
    id = UUID()


class TestUUID(TestCase):
    def test_deserialize(self):
        id = str(uuid.uuid4())
        data, _ = ObjectWithUUID().load({'id': id})
        self.assertEqual(data['id'], id)

    def test_serialize(self):
        id = str(uuid.uuid4())
        data, _ = ObjectWithUUID().dump({'id': id})
        self.assertEqual(data['id'], id)

    def test_deserialize_errors(self):
        id = '123456'
        _, errs = ObjectWithUUID().load({'id': id})
        self.assertEqual(errs['id'], ['Not a valid UUID.'])

    def test_serialize_errors(self):
        id = '123456'
        _, errs = ObjectWithUUID().dump({'id': id})
        self.assertEqual(errs['id'], ['Not a valid UUID.'])


class ObjectWithObjectID(Schema):
    id = ObjectId()


class TestObjectId(TestCase):
    def test_deserialize(self):
        id = '5550f21512921d007563c3b0'
        data, _ = ObjectWithObjectID().load({'id': id})
        self.assertEqual(data['id'], id)

    def test_serialize(self):
        id = '5550f21512921d007563c3b0'
        data, _ = ObjectWithObjectID().dump({'id': id})
        self.assertEqual(data['id'], id)

    def test_deserialize_errors(self):
        id = '123456'
        _, errs = ObjectWithObjectID().load({'id': id})
        self.assertEqual(errs['id'], ['Not a valid ObjectID.'])

    def test_serialize_errors(self):
        id = '123456'
        _, errs = ObjectWithObjectID().dump({'id': id})
        self.assertEqual(errs['id'], ['Not a valid ObjectID.'])


class ObjectWithSkip(Schema):
    skip = Skip()


class TestSkip(TestCase):
    def test_deserialize(self):
        data, _ = ObjectWithSkip().load({'skip': 40})
        self.assertEqual(data['skip'], 40)

        # Works with strings
        data, _ = ObjectWithSkip().load({'skip': '40'})
        self.assertEqual(data['skip'], 40)

        # Skip defaults to 0
        data, _ = ObjectWithSkip().load({})
        self.assertEqual(data['skip'], 0)

    def test_serialize(self):
        data, _ = ObjectWithSkip().dump({'skip': 40})
        self.assertEqual(data['skip'], 40)

        # Skip defaults to 0
        data, _ = ObjectWithSkip().dump({})
        self.assertEqual(data['skip'], 0)

    def test_deserialize_errors(self):
        _, errs = ObjectWithSkip().load({'skip': -1})
        self.assertEqual(errs['skip'], ['Skip must be 0 or positive integer.'])

    def test_serialize_errors(self):
        _, errs = ObjectWithSkip().dump({'skip': 'hello'})
        self.assertEqual(errs['skip'], ['Skip must be 0 or positive integer.'])


class ObjectWithLimit(Schema):
    limit = Limit()


class TestLimit(flask_testing.TestCase):
    PAGINATION_LIMIT_MAX = 100

    def create_app(self):
        # We need to initialize an app so we can get the default limit
        app = Flask(__name__)
        Toolbox(app, pagination_limit_max=self.PAGINATION_LIMIT_MAX)
        return app

    def test_deserialize(self):
        data, _ = ObjectWithLimit().load({'limit': 50})
        self.assertEqual(data['limit'], 50)

        # Works with strings
        data, _ = ObjectWithLimit().load({'limit': '50'})
        self.assertEqual(data['limit'], 50)

        # Limit defaults to the toolbox's default
        data, _ = ObjectWithLimit().load({})
        self.assertEqual(data['limit'], self.PAGINATION_LIMIT_MAX)

        class ObjectWithNullDefaultLimit(Schema):
            limit = Limit(default=None)

        # Limit can be made none
        data, _ = ObjectWithNullDefaultLimit().load({})
        self.assertIsNone(data['limit'])

    def test_serialize(self):
        data, _ = ObjectWithLimit().dump({'limit': 50})
        self.assertEqual(data['limit'], 50)

    def test_deserialize_errors(self):
        _, errs = ObjectWithLimit().load({'limit': 0})
        self.assertEqual(errs['limit'], ['Limit must be a positive integer.'])

        _, errs = ObjectWithLimit().load({'limit': self.PAGINATION_LIMIT_MAX + 1})
        self.assertEqual(errs['limit'], ['Maximum limit is {}'.format(self.PAGINATION_LIMIT_MAX)])

    def test_serialize_errors(self):
        _, errs = ObjectWithLimit().dump({'limit': 'hello'})
        self.assertEqual(errs['limit'], ['Limit must be a positive integer.'])