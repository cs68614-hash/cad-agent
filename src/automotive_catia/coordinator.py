"""One catalog, one STA, one bound document. No generic code/COM executor."""
from __future__ import annotations
import asyncio
import copy
import importlib
import json
import uuid
from pathlib import Path
from jsonschema import validate
from .runtime import Runtime
from .safety import PathPolicy, SafetyError, failure, normalize_result, validate_finite

DISABLED = {
 'daiemon__catia_connect': 'Use auto_connect: attach only, no automatic application launch.',
 'daiemon__catia_disconnect': 'Shared connection lifecycle is server-owned.',
 'hub__catia_connect': 'Use auto_connect: attach only.',
 'daiemon__catia_coincidence_constraint': 'Upstream ignores element1/element2; geometric binding not implemented.',
 'daiemon__catia_offset_constraint': 'Geometric reference binding requires live validation; component-level fallback disabled.',
 'daiemon__catia_angle_constraint': 'Geometric reference binding requires live validation.',
 'daiemon__catia_measure_distance': 'Upstream unit multiplier is unverified; use Hub quality data with documented units.',
 'daiemon__catia_get_bounding_box': 'Vertex sampling is not an exact surface bounding box.',
 'daiemon__catia_screenshot': 'Upstream dimensions/format claims unverified; prefer hub screenshot BMP.',
}
READ_PREFIXES = ('catia_list_', 'catia_get_', 'catia_inspect_', 'catia_health_', 'catia_operation_', 'catia_surface_capabilities', 'catia_analysis_catalog', 'catia_check_surface_quality')
GLOBAL_NAMES = {'catia_list_documents','catia_health_check','catia_operation_status','catia_operation_status','catia_new_part','catia_new_product','catia_create_part','catia_create_product','catia_open_document'}
PATH_KEYS = {'path','file_path','catalog_path','output_path','report_path','directory','output_dir','material_catalog','catalog_file','folder'}

# Audited against all 153 pinned source schemas. Geometry profile is NOT a file path.
TOOL_PATH_FIELDS = {
 'daiemon__catia_add_component': ('file_path',),
 'daiemon__catia_open_document': ('file_path',),
 'daiemon__catia_save_document': ('file_path',),
 'daiemon__catia_export': ('file_path',),
 'daiemon__catia_screenshot': ('file_path',),
 'daiemon__catia_create_design_table': ('file_path',),
 'hub__catia_open_document': ('path',),
 'hub__catia_save_active': ('path',),
 'hub__catia_export_active': ('path',),
 'hub__catia_create_parametric_part': ('output_path',),
 'hub__catia_add_components': ('paths',),
 'hub__catia_list_materials': ('catalog_path',),
 'hub__catia_apply_material': ('catalog_path',),
 'hub__catia_capture_view': ('path',),
 'hub__catia_create_analysis_document': ('output_path',),
 'hub__catia_export_analysis_result_data': ('folder',),
 'hub__catia_build_analysis_report': ('folder',),
}
RECOMMENDED = {
 'surface_points':'hub__catia_create_3d_points',
 'surface_spline':'hub__catia_create_spline',
 'surface_loft':'hub__catia_create_loft',
 'surface_offset':'daiemon__catia_gsd_offset_surface',
 'surface_trim':'daiemon__catia_gsd_trim',
 'surface_join':'hub__catia_join_surfaces',
 'surface_heal':'hub__catia_heal_surfaces',
 'surface_quality':'hub__catia_check_surface_quality',
 'surface_thicken':'hub__catia_thick_surface',
 'safe_export':'hub__catia_export_active',
 'pocket':'hub__catia_add_pocket',
 'edge_fillet':'hub__catia_add_edge_fillet',
 'screenshot_bmp':'hub__catia_capture_view',
}

def schema(properties=None, required=()):
 return {'type':'object','properties':properties or {},'required':list(required),'additionalProperties':False}

def tool(name,description,properties=None,required=()):
 return {'name':name,'description':description,'inputSchema':schema(properties,required)}

class Coordinator:
 def __init__(self, workspace: Path, mock: bool=False):
  self.workspace=Path(workspace).resolve();self.workspace.mkdir(parents=True,exist_ok=True)
  self.mock=mock;self.instance=uuid.uuid4().hex
  journal=self.workspace/'.automotive-catia-journal.sqlite3'
  self.policy=PathPolicy([self.workspace],reserved=[str(journal)+suffix for suffix in ('','-wal','-shm','-journal','.lock')])
  self.runtime=Runtime(self.workspace/'.automotive-catia-journal.sqlite3')
  self.connection=None;self.hub=None;self.modules={};self.bound=None;self.token=None;self.revision=0;self.requires_reset=False
  self.catalog={}
  base=Path(__file__).parent
  for row in json.loads((base/'daiemon_catalog.json').read_text(encoding='utf-8')):
   row['source_name']=row['name'];row['name']='daiemon__'+row['name'];row['source']='daiemon';self.catalog[row['name']]=row
  for row in json.loads((base/'hub_catalog.json').read_text(encoding='utf-8')):
   self.catalog[row['name']]=row
  self.native=[
   tool('auto_catalog','Full provenance/status catalog; registered is not live validated.'),
   tool('auto_session','Runtime state and binding; no COM access.'),
   tool('auto_connect','Attach to already running CATIA only. Does not launch it.'),
   tool('auto_bind_document','Bind current active document after matching name; invalidate old tokens.',{'confirm_name':{'type':'string'}},['confirm_name']),
   tool('auto_acknowledge_unknown','Acknowledge external inspection; NOT rollback or proof of safe state.',{'acknowledge':{'type':'boolean'}},['acknowledge']),
   tool('auto_surface_pipeline','Ordered GSD steps, stop at first failure; NOT an atomic transaction.',{'steps':{'type':'array','minItems':1,'maxItems':20,'items':schema({'tool':{'type':'string'},'arguments':{'type':'object'}},['tool','arguments'])},'request_id':{'type':'string'},'document_token':{'type':'string'}},['steps','request_id','document_token'])
  ]

 def list_tools(self):
  result=copy.deepcopy(self.native)
  for row in self.catalog.values():
   item={k:copy.deepcopy(row[k]) for k in ('name','description','inputSchema')}
   s=item['inputSchema'];s.setdefault('properties',{})
   s['properties']['request_id']={'type':'string','maxLength':256}
   s['properties']['document_token']={'type':'string'}
   s['additionalProperties']=False
   required=s.setdefault('required',[])
   if self._mutating(row) and 'request_id' not in required:required.append('request_id')
   if row['source_name'] not in GLOBAL_NAMES and 'document_token' not in required:required.append('document_token')
   if row['name']=='hub__catia_health_check':item['description']='Lightweight unified health without COM import; detailed upstream Windows installation probe is deferred.'
   if row['name'] in DISABLED:item['description']='[DISABLED: '+DISABLED[row['name']]+'] '+item['description']
   result.append(item)
  return result

 def _mutating(self,row):
  # Names are not sufficient: quality updates geometry, material inventory opens
  # documents, and topology/inertia inspection changes Selection/SPA collections.
  if row['source_name'] in {'catia_check_surface_quality','catia_list_materials','catia_inspect_edges','catia_list_edges','catia_list_faces','catia_get_inertia'}:return True
  return not row['source_name'].startswith(READ_PREFIXES)

 async def call(self,name,args):
  try:
   validate_finite(args)
   definitions={t['name']:t for t in self.list_tools()}
   if name not in definitions:return failure('UNKNOWN_TOOL',name)
   validate(args,definitions[name]['inputSchema'])
   if name in DISABLED:return failure('DISABLED',DISABLED[name])
   if name=='auto_catalog':return {'ok':True,'source_counts':{'daiemon':98,'hub':55},'disabled':DISABLED,'enabled_source_entries':len(self.catalog)-len(DISABLED),'recommended':RECOMMENDED,'live_verified':False,'tools':[{'name':r['name'],'source':r['source'],'enabled':r['name'] not in DISABLED,'geometry_validation':'not_run'} for r in self.catalog.values()]}
   if name in {'auto_session','hub__catia_operation_status'}:return {'ok':True,**self.runtime.state(),'document_token':self.token,'revision':self.revision,'mock':self.mock,'session_id':self.instance}
   if name=='hub__catia_health_check':return {'ok':True,'runtime':self.runtime.state(),'connected':getattr(self.connection,'app',None) is not None,'mock':self.mock,'installation_probe':'Deferred: use local Windows installation checks; no implicit COM import or launch','live_verified':False}
   if name=='auto_acknowledge_unknown':
    result=self.runtime.acknowledge_unknown(args['acknowledge'])
    if result.get('ok'):self.token=None;self.requires_reset=True
    return result
   mutating=name=='auto_surface_pipeline' or (name in self.catalog and self._mutating(self.catalog[name]))
   request=args.get('request_id'); guard=args.get('document_token','')
   return await asyncio.to_thread(self.runtime.call,name,args,lambda:self._invoke_guarded(name,args),request_id=request,document_token=self.instance+':'+guard,mutating=mutating)
  except Exception as e:return failure(getattr(e,'code','INVALID_ARGUMENT'),str(e))

 def _invoke_guarded(self,name,args):
  try:return self._invoke(name,args)
  except SafetyError as e:return failure(e.code,str(e))

 def _connect(self):
  if self.mock:return {'ok':True,'mock':True,'message':'Mock mode; no CATIA attached.'}
  if self.connection is not None and self.connection.app is not None:
   return {'ok':True,'message':'Already attached; shared session unchanged'}
  if self.connection is None:
   from .vendor.daiemon.connection import CATIAConnection
   class AttachedConnection(CATIAConnection):
    def connect(this):
     import win32com.client
     this.app=win32com.client.GetActiveObject('CATIA.Application')
     return 'Attached to running CATIA'
    def ensure_connected(this):
     if this.app is None:raise RuntimeError('Call auto_connect first; automatic launching is prohibited')
    def disconnect(this):raise RuntimeError('Connection lifecycle is server owned')
   self.connection=AttachedConnection()
  return {'ok':True,'message':self.connection.connect(),'live_verified':False}

 def _active(self):
  if self.mock:return {'name':'MockPart','identity':'mock'}
  if self.connection is None:raise SafetyError('NOT_CONNECTED','Call auto_connect first')
  d=self.connection.active_document
  return d

 def _bind(self,name):
  d=self._active();actual=d['name'] if self.mock else str(d.Name)
  if actual!=name:raise SafetyError('DOCUMENT_MISMATCH','Active document name does not match confirmation')
  if self.bound is None or d!=self.bound or self.requires_reset:
   self.modules.clear();self.hub=None;self.requires_reset=False
  self.bound=d;self.revision+=1;self.token=uuid.uuid4().hex
  return {'ok':True,'document_name':actual,'next_document_token':self.token,'revision':self.revision,'mock':self.mock}

 def _guard(self,args):
  if not self.token or args.get('document_token')!=self.token:raise SafetyError('STALE_DOCUMENT','Bind current document and use latest document token')
  d=self._active()
  if not self.mock and d!=self.bound:raise SafetyError('ACTIVE_DOCUMENT_CHANGED','Active document changed; rebind explicitly')
  return d

 def _paths(self,args):
  def walk(v):
   if isinstance(v,dict):
    return {k:(str(self.policy.resolve(x)) if x and isinstance(x,str) and (k in PATH_KEYS or k.endswith('_path')) else walk(x)) for k,x in v.items()}
   if isinstance(v,list):return [walk(x) for x in v]
   return v
  return walk(args)

 def _tool_paths(self,name,args):
  args=copy.deepcopy(args)
  for key in TOOL_PATH_FIELDS.get(name,()):
   value=args.get(key)
   if value is None:continue
   if isinstance(value,list):args[key]=[str(self.policy.resolve(p)) for p in value]
   else:args[key]=str(self.policy.resolve(value))
  if name=='hub__catia_export_analysis_result_data':
   leaf=args.get('file_name','')
   if not leaf or any(c in leaf for c in ('/',chr(92),':')) or leaf in ('.','..'):
    raise SafetyError('PATH_DENIED','file_name must be a plain basename')
  return self._paths(args)

 def _invoke(self,name,args):
  if name=='auto_connect':return self._connect()
  if name=='auto_bind_document':return self._bind(args['confirm_name'])
  if name=='auto_surface_pipeline':return self._pipeline(args)
  row=self.catalog[name];source_name=row['source_name'];mutating=self._mutating(row)
  if not self.mock and self.connection is None:raise SafetyError('NOT_CONNECTED','Call auto_connect first')
  if source_name not in GLOBAL_NAMES:self._guard(args)
  clean=self._tool_paths(name,{k:v for k,v in args.items() if k not in ('document_token','request_id')})
  if ('save' in source_name and not clean.get('path') and not clean.get('file_path')) or ('close' in source_name and clean.get('save')):
   if not self.mock:
    full=str(self._active().FullName)
    if not full or not Path(full).is_absolute():raise SafetyError('EXPLICIT_SAVE_PATH_REQUIRED','Unsaved document requires explicit allowed SaveAs path')
    self.policy.resolve(full)
  if self.mock:
   return {'ok':False,'code':'MOCK_ONLY','message':'Mock transport does not execute or validate CATIA geometry. Use unit fakes for adapter tests.','mock':True,'effects':{'outcome':'not_executed','modified':False}}
  result=self._execute_source(row,clean)
  if source_name=='catia_check_surface_quality' and isinstance(result,dict) and any(e.get('update_ok') is False or e.get('measurement_error') for e in result.get('elements',[]) if isinstance(e,dict)):
   result={'ok':False,'error':'Surface quality update or measurement failed','data':result,'effects':{'outcome':'possibly_modified','rollback':False}}
  result=normalize_result(result)
  result['live_geometry_verified']=False
  if mutating:
   self.revision+=1;self.token=uuid.uuid4().hex
   result['next_document_token']=self.token;result['revision']=self.revision
   if source_name in GLOBAL_NAMES or source_name in {'catia_close_document','catia_close_active'} or not self._binding_current():
    self.bound=None;self.token=None;self.modules.clear();self.hub=None;result['next_document_token']=None;result['requires_binding']=True
  return result

 def _binding_current(self):
  if self.bound is None:return False
  if self.mock:return True
  try:return self._active()==self.bound
  except Exception:return False

 def _execute_source(self,row,args):
  if row['source']=='daiemon':
   module=row['module']
   if module not in self.modules:
    imported=importlib.import_module('.vendor.daiemon.tools.'+module,__package__)
    self.modules[module]=getattr(imported,row['class'])(self.connection)
   return self.modules[module].execute(row['source_name'],args)
  if self.hub is None:
   from .hub_adapter import HubAdapter
   self.hub=HubAdapter(self.connection,self.workspace)
  return self.hub.execute(row['name'],args)

 def _pipeline(self,args):
  self._guard(args);steps=args['steps']
  allowed={name for name,r in self.catalog.items() if (r.get('module')=='gsd' or any(s in r['source_name'] for s in ('surface','spline','loft','geometrical_set','3d_points','offset_plane','boundary','healing','thicken'))) and name not in DISABLED}
  # Validate every step before the first mutation. No recursive Runtime.call.
  definitions={t['name']:t for t in self.list_tools()}
  for step in steps:
   if step['tool'] not in allowed:raise SafetyError('PIPELINE_TOOL_DENIED',step['tool'])
   row=definitions[step['tool']];test={**step['arguments'],'document_token':self.token,'request_id':args['request_id']}
   validate(test,row['inputSchema']);self._tool_paths(step['tool'],test)
  completed=[]
  for index,step in enumerate(steps):
   try:result=self._invoke(step['tool'],{**step['arguments'],'document_token':self.token,'request_id':args['request_id']})
   except Exception as e:result=failure('STEP_FAILED',str(e))
   completed.append({'index':index,'tool':step['tool'],'result':result})
   if not result.get('ok'):return {'ok':False,'code':'PIPELINE_PARTIAL','steps':completed,'failed_step':index,'effects':{'outcome':'possibly_modified','modified':None,'rollback':False},'next_document_token':self.token}
  return {'ok':True,'steps':completed,'next_document_token':self.token,'effects':{'modified':True,'rollback':False},'quality_verified':False}

 def close(self):self.runtime.close()
