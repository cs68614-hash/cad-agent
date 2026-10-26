"""Offline safety/catalog tests; never connect to CATIA."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from automotive_catia.coordinator import Coordinator, DISABLED

class CoordinatorTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.c=Coordinator(Path(self.temp.name),mock=True)
 def tearDown(self):
  self.c.runtime.close(wait=True);self.temp.cleanup()
 def call(self,name,args=None):return asyncio.run(self.c.call(name,args or {}))
 def bind(self):return self.call('auto_bind_document',{'confirm_name':'MockPart'})['next_document_token']
 def test_catalog(self):
  tools=self.c.list_tools();self.assertEqual(len(tools),159);self.assertEqual(len({t['name'] for t in tools}),159)
  self.assertEqual(len(self.c.catalog),153);self.assertTrue(set(DISABLED)<=self.c.catalog.keys())
 def test_all_daiemon_live_definitions_match_static_catalog(self):
  import importlib
  checked=set()
  for row in self.c.catalog.values():
   if row['source']!='daiemon' or row['module'] in checked:continue
   checked.add(row['module'])
   module=importlib.import_module('automotive_catia.vendor.daiemon.tools.'+row['module'])
   actual=getattr(module,row['class'])(None).get_tool_definitions()
   for definition in actual:
    stored=self.c.catalog['daiemon__'+definition['name']]
    self.assertEqual(definition['inputSchema'],stored['inputSchema'])
  self.assertEqual(len(checked),10)
 def test_journal_paths_reserved(self):
  for suffix in ('','-wal','-shm','-journal','.lock'):
   with self.assertRaises(Exception):self.c._tool_paths('daiemon__catia_save_document',{'file_path':'.automotive-catia-journal.sqlite3'+suffix})
 def test_status_and_health_before_connection(self):
  for name in ('hub__catia_health_check','hub__catia_operation_status'):
   self.assertTrue(self.call(name)['ok'])
  self.assertFalse(self.c.runtime.state()['blocked'])
 def test_bind_and_old_token(self):
  old=self.bind();self.bind()
  r=self.call('daiemon__catia_gsd_point',{'x':1,'y':2,'z':3,'document_token':old,'request_id':'old'})
  self.assertFalse(r['ok']);self.assertFalse(self.c.runtime.state()['blocked'])
 def test_missing_mutation_id(self):
  r=self.call('daiemon__catia_new_part',{});self.assertFalse(r['ok'])
 def test_mock_never_claims_geometry(self):
  r=self.call('daiemon__catia_new_part',{'request_id':'mock'})
  self.assertFalse(r['ok']);self.assertTrue(r['mock'])
 def test_nonfinite(self):
  r=self.call('daiemon__catia_gsd_point',{'x':float('nan'),'y':0,'z':0,'document_token':self.bind(),'request_id':'nan'})
  self.assertFalse(r['ok'])
 def test_path_escape_before_backend(self):
  r=self.call('daiemon__catia_open_document',{'file_path':'../escape.CATPart','request_id':'escape'})
  self.assertFalse(r['ok']);self.assertFalse(self.c.runtime.state()['blocked'])
 def test_pipeline_denies_non_surface(self):
  r=self.call('auto_surface_pipeline',{'steps':[{'tool':'daiemon__catia_save_document','arguments':{}}],'document_token':self.bind(),'request_id':'bad-pipeline'})
  self.assertFalse(r['ok'])
 def test_schema_source_metadata_not_sent(self):
  self.assertTrue(all(set(t)=={'name','description','inputSchema'} for t in self.c.list_tools()))

class IntegrationGuardTests(unittest.TestCase):
 def setUp(self):
  from types import SimpleNamespace
  self.temp=tempfile.TemporaryDirectory();self.c=Coordinator(Path(self.temp.name))
  self.doc=SimpleNamespace(Name='Part1',FullName=str(Path(self.temp.name)/'Part1.CATPart'))
  self.c.connection=SimpleNamespace(active_document=self.doc)
  self.calls=[]
  def execute(row,args):self.calls.append((row['name'],args));return {'created':'Feature'}
  self.c._execute_source=execute
 def tearDown(self):self.c.runtime.close(wait=True);self.temp.cleanup()
 def call(self,name,args=None):return asyncio.run(self.c.call(name,args or {}))
 def bind(self):return self.call('auto_bind_document',{'confirm_name':'Part1'})['next_document_token']
 def test_mutation_token_and_replay(self):
  args={'x':1,'y':2,'z':3,'document_token':self.bind(),'request_id':'one'}
  result=self.call('daiemon__catia_gsd_point',args)
  self.assertTrue(result['ok']);self.assertNotEqual(result['next_document_token'],args['document_token'])
  again=self.call('daiemon__catia_gsd_point',args);self.assertTrue(again['replayed']);self.assertEqual(len(self.calls),1)
  bad=self.call('daiemon__catia_gsd_point',{**args,'x':9});self.assertFalse(bad['ok'])
 def test_external_document_switch_prevents_execution(self):
  from types import SimpleNamespace
  token=self.bind();self.c.connection.active_document=SimpleNamespace(Name='Other',FullName='other')
  result=self.call('daiemon__catia_gsd_point',{'x':0,'y':0,'z':0,'document_token':token,'request_id':'switch'})
  self.assertFalse(result['ok']);self.assertEqual(self.calls,[])
 def test_rebind_other_document_discards_cached_sketch_handles(self):
  from types import SimpleNamespace
  self.bind()
  old_factory=object();self.c.modules['sketcher']=SimpleNamespace(_active_factory=old_factory)
  self.c.modules['gsd']=SimpleNamespace(_active_geoset_name='OldSet')
  self.c.connection.active_document=SimpleNamespace(Name='Part2',FullName='part2')
  result=self.call('auto_bind_document',{'confirm_name':'Part2'})
  self.assertTrue(result['ok']);self.assertEqual(self.c.modules,{})
 def test_ack_rebind_discards_cached_handles_on_worker(self):
  self.bind();self.c.modules['sketcher']=object()
  self.call('auto_acknowledge_unknown',{'acknowledge':True})
  self.bind();self.assertEqual(self.c.modules,{})
 def test_source_switching_document_invalidates_binding(self):
  from types import SimpleNamespace
  def execute(row,args):
   self.c.connection.active_document=SimpleNamespace(Name='NewAnalysis',FullName='new')
   return {'created':'analysis'}
  self.c._execute_source=execute
  result=self.call('daiemon__catia_gsd_point',{'x':0,'y':0,'z':0,'document_token':self.bind(),'request_id':'switch-inside'})
  self.assertTrue(result['ok']);self.assertIsNone(result['next_document_token']);self.assertTrue(result['requires_binding'])
 def test_implicit_save_outside_workspace_denied(self):
  token=self.bind();self.doc.FullName='/tmp/outside.CATPart'
  result=self.call('daiemon__catia_save_document',{'document_token':token,'request_id':'save'})
  self.assertFalse(result['ok']);self.assertEqual(self.calls,[])
 def test_component_path_list_fully_guarded(self):
  token=self.bind()
  result=self.call('hub__catia_add_components',{'paths':['../bad.CATPart'],'document_token':token,'request_id':'paths'})
  self.assertFalse(result['ok']);self.assertEqual(self.calls,[])
 def test_pipeline_single_worker_and_partial_failure(self):
  import threading
  ids=[]
  def execute(row,args):
   ids.append(threading.get_ident())
   if len(ids)==2:raise RuntimeError('mock COM failure after first step')
   return {'created':'Point'}
  self.c._execute_source=execute
  steps=[{'tool':'daiemon__catia_gsd_point','arguments':{'x':i,'y':0,'z':0}} for i in range(3)]
  result=self.call('auto_surface_pipeline',{'steps':steps,'document_token':self.bind(),'request_id':'pipeline'})
  self.assertFalse(result['ok']);self.assertEqual(result['failed_step'],1);self.assertEqual(len(ids),2)
  self.assertEqual(len(set(ids)),1);self.assertTrue(self.c.runtime.state()['blocked'])
 def test_quality_and_material_inventory_require_mutation_guards(self):
  for name in ('hub__catia_check_surface_quality','hub__catia_list_materials','daiemon__catia_get_inertia'):
   self.assertTrue(self.c._mutating(self.c.catalog[name]))
   schema=next(t['inputSchema'] for t in self.c.list_tools() if t['name']==name)
   self.assertIn('request_id',schema['required'])
 def test_failed_quality_update_stops_pipeline(self):
  self.c._execute_source=lambda row,args:{'elements':[{'name':'Surface','update_ok':False,'update_error':'failed'}]}
  props=self.c.catalog['hub__catia_check_surface_quality']['inputSchema']['properties']
  args={'element_names':['Surface']}
  self.assertIn('element_names',props)
  result=self.call('hub__catia_check_surface_quality',{**args,'document_token':self.bind(),'request_id':'quality'})
  self.assertFalse(result['ok']);self.assertTrue(self.c.runtime.state()['blocked'])
 def test_no_effect_is_not_success(self):
  self.c._execute_source=lambda row,args:'FEATURE_NO_EFFECT: pocket removed no material'
  result=self.call('daiemon__catia_pocket',{'depth':2,'document_token':self.bind(),'request_id':'pocket'})
  self.assertFalse(result['ok']);self.assertTrue(self.c.runtime.state()['blocked'])

if __name__=='__main__':unittest.main()
