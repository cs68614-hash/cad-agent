"""Offline adapters/primitive tests. No Windows COM or real geometry validation."""
import ast
import inspect
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from automotive_catia.hub_adapter import HubAdapter, _DirectSession
from automotive_catia.vendor.daiemon.tools.gsd import GSDTools
from automotive_catia.vendor.daiemon.tools.part_design import PartDesignTools


def sample(schema):
    if 'default' in schema:
        return schema['default']
    if 'anyOf' in schema:
        return sample(next(s for s in schema['anyOf'] if s.get('type') != 'null'))
    return {'string': 'test', 'boolean': False, 'integer': 1, 'number': 1.0,
            'array': [], 'object': {}, 'null': None}.get(schema.get('type'), 'test')


class SignatureExecutor:
    """Binds every wrapper call against AST-read real executor signatures."""
    def __init__(self):
        source = Path(__file__).parents[1] / 'src/automotive_catia/vendor/hub/executor.py'
        cls = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.ClassDef))
        self.signatures = {}
        self.calls = []
        for method in cls.body:
            if not isinstance(method, ast.FunctionDef):
                continue
            defaults = [inspect.Parameter.empty] * (len(method.args.args) - len(method.args.defaults))
            defaults += [ast.literal_eval(n) for n in method.args.defaults]
            parameters = [inspect.Parameter(a.arg, inspect.Parameter.POSITIONAL_OR_KEYWORD, default=d)
                          for a, d in zip(method.args.args, defaults) if a.arg != 'self']
            for a, d in zip(method.args.kwonlyargs, method.args.kw_defaults):
                parameters.append(inspect.Parameter(a.arg, inspect.Parameter.KEYWORD_ONLY,
                    default=inspect.Parameter.empty if d is None else ast.literal_eval(d)))
            if method.args.kwarg:
                parameters.append(inspect.Parameter(method.args.kwarg.arg, inspect.Parameter.VAR_KEYWORD))
            self.signatures[method.name] = inspect.Signature(parameters)

    def __getattr__(self, name):
        signature = self.signatures[name]
        def call(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            self.calls.append((name, bound.arguments))
            return {'delegated': name}
        return call


class HubAdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = HubAdapter(SimpleNamespace(app=object()), tempfile.gettempdir())
        self.fake = SignatureExecutor()
        self.adapter._executor = self.fake

    def test_catalog_count_and_unique_names(self):
        defs = self.adapter.definitions()
        self.assertEqual(len(defs), 55)
        self.assertEqual(len({d['name'] for d in defs}), 55)
        defs[0]['name'] = 'changed'
        self.assertNotEqual(self.adapter.definitions()[0]['name'], 'changed')

    def test_every_enabled_wrapper_binds_actual_executor_signature(self):
        for definition in self.adapter.definitions():
            name = definition['name']
            if name == 'hub__catia_connect':
                continue
            with self.subTest(tool=name):
                props = definition['inputSchema']['properties']
                args = {key: sample(props[key]) for key in definition['inputSchema']['required']}
                before = len(self.fake.calls)
                result = self.adapter.execute(name, args)
                self.assertEqual(len(self.fake.calls), before + 1)
                self.assertIn('delegated', result)

    def test_connect_disabled_without_creating_executor(self):
        self.adapter._executor = None
        with self.assertRaisesRegex(RuntimeError, 'DISABLED'):
            self.adapter.execute('hub__catia_connect', {'start_if_missing': True})
        self.assertIsNone(self.adapter._executor)

    def test_direct_session_uses_exact_injected_application(self):
        app = object()
        session = _DirectSession(SimpleNamespace(app=app))
        observed = []
        self.assertEqual(session.run('id', lambda a: observed.append(a) or {'done': True}), {'done': True})
        self.assertIs(observed[0], app)
        self.assertFalse(hasattr(session, '_thread'))

    def test_disconnected_direct_session_rejects_without_call(self):
        fn = Mock()
        with self.assertRaisesRegex(RuntimeError, 'NOT_CONNECTED'):
            _DirectSession(SimpleNamespace(app=None)).run('id', fn)
        fn.assert_not_called()

    def test_wrapper_errors_are_not_swallowed(self):
        self.adapter._executor = SimpleNamespace(create_part=Mock(side_effect=RuntimeError('COM failure')))
        with self.assertRaisesRegex(RuntimeError, 'COM failure'):
            self.adapter.execute('hub__catia_create_part', {'title': 'X'})


class DaiemonPrimitiveTests(unittest.TestCase):
    def setUp(self):
        self.connection = Mock()
        self.part = Mock()
        self.connection.get_active_part.return_value = self.part
        self.geoset = Mock()
        self.geoset.Name = 'Surfaces'
        self.part.HybridBodies.Count = 1
        self.part.HybridBodies.Item.return_value = self.geoset
        self.tools = GSDTools(self.connection)

    def test_point_creates_appends_updates_actual_primitive(self):
        point = SimpleNamespace(Name='Point.1')
        self.part.HybridShapeFactory.AddNewPointCoord.return_value = point
        result = self.tools.execute('catia_gsd_point', {'x': 1, 'y': 2, 'z': 3, 'name': 'Datum'})
        self.part.HybridShapeFactory.AddNewPointCoord.assert_called_once_with(1, 2, 3)
        self.geoset.AppendHybridShape.assert_called_once_with(point)
        self.part.UpdateObject.assert_called_once_with(point)
        self.assertEqual(point.Name, 'Datum')
        self.assertIn('Datum', result)

    def test_offset_factory_argument_orientation(self):
        feature = SimpleNamespace(Name='Offset.1')
        self.part.HybridShapeFactory.AddNewOffset.return_value = feature
        with patch.object(self.tools, '_ref', return_value='surface-ref'):
            self.tools.execute('catia_gsd_offset_surface', {'surface': 'Skin', 'offset': 2.5, 'reverse': True})
        self.part.HybridShapeFactory.AddNewOffset.assert_called_once_with('surface-ref', 2.5, True, 0)
        self.part.UpdateObject.assert_called_once_with(feature)

    def test_failed_update_does_not_return_success(self):
        self.part.UpdateObject.side_effect = RuntimeError('invalid geometry')
        self.part.HybridShapeFactory.AddNewPointCoord.return_value = SimpleNamespace(Name='P')
        with self.assertRaisesRegex(RuntimeError, 'update failed'):
            self.tools.execute('catia_gsd_point', {'x': 1, 'y': 2, 'z': 3})

    def test_pocket_no_effect_is_exposed_for_outer_normalization(self):
        tools = PartDesignTools(self.connection)
        pocket = SimpleNamespace(Name='Pocket.1', DirectionOrientation=0)
        self.part.ShapeFactory.AddNewPocket.return_value = pocket
        with patch.object(tools, '_get_last_sketch', return_value=object()), \
             patch.object(tools, '_body_volume_mm3', return_value=1000), \
             patch('automotive_catia.vendor.daiemon.tools.part_design._force_solid_inwork'):
            result = tools.execute('catia_pocket', {'depth': 5, 'direction': 'normal'})
        self.assertTrue(result.startswith('FEATURE_NO_EFFECT:'))


if __name__ == '__main__':
    unittest.main()
