import copy
import importlib.util
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/differt_bridge'))
import comparison as c


def study(engine='sionna', gain=-60, paths=1):
    prefix = '' if engine == 'sionna' else 'DiffeRT_'
    tx,rx=prefix+'TX',prefix+'RX'
    values = {'solver/'+k: v for k,v in dict(frequency_hz=3.5e9,max_depth=1,los=True,
              specular_reflection=True,diffuse_reflection=False,refraction=False,
              diffraction=False,mobility_doppler=False).items()}
    for role,name,pos in [('transmitters',tx,(-2,0,1)),('receivers',rx,(2,0,1))]:
        for i,x in enumerate(pos): values[f'device/{role}/{name}/position/{i}']=x
        for i in range(3): values[f'device/{role}/{name}/orientation_{engine}_rad/{i}']=0
    values['material/concrete/model']='ITU'
    context={'antenna/'+role+'/'+key:value for role in ('tx','rx') for key,value in
             dict(pattern='iso',num_rows=1,num_cols=1,vertical_spacing=.5,horizontal_spacing=.5,
                  polarization='V',polarization_model='tr38901_2').items()}
    return {'schema':engine+'_parameter_study','schema_version':1,'run_id':engine,
            'context':context,
            'geometry_evidence':{'1':{'sha256':'same','method':'test'}},
            'records':[dict(frame=1,pair=0,tx=tx,rx=rx,values=values,
                            metrics=dict(path_count=paths,total_power_db=gain,first_arrival_ns=12.))]}


def test_pair_by_endpoint_not_index():
    a,b=study(),study('differt',-61)
    b['records'][0]['pair']=7
    result=c.compare_studies(a,b)
    row=next(r for r in result['rows'] if r['metric']=='total_power_db')
    assert row['differt_minus_sionna']==-1
    assert row['status']=='matched_inputs'


@pytest.mark.parametrize('kind',['frequency','position','geometry','antenna'])
def test_mismatched_inputs_are_flagged(kind):
    a,b=study(),study('differt')
    if kind=='frequency':b['records'][0]['values']['solver/frequency_hz']=4e9
    if kind=='position':b['records'][0]['values']['device/receivers/DiffeRT_RX/position/0']=3
    if kind=='geometry':b['geometry_evidence']['1']['sha256']='different'
    if kind=='antenna':b['context']['antenna/tx/num_rows']=2
    assert c.compare_studies(a,b)['pairs'][0]['status']=='inputs_differ'


def test_no_path_values_not_fabricated():
    result=c.compare_studies(study(paths=0),study('differt',paths=0))
    assert next(r for r in result['rows'] if r['metric']=='path_count')['differt_minus_sionna']==0
    assert next(r for r in result['rows'] if r['metric']=='total_power_db')['sionna'] is None
    assert next(r for r in result['rows'] if r['metric']=='first_arrival_ns')['differt_minus_sionna'] is None


def test_missing_links_and_missing_geometry():
    a,b=study(),study('differt')
    b.pop('geometry_evidence')
    assert c.compare_studies(a,b)['pairs'][0]['status']=='partially_verified'
    b['records'][0]['rx']='AnotherRX'
    assert all(p['status']=='missing_link' for p in c.compare_studies(a,b)['pairs'])


def test_ambiguous_names_raise():
    a,b=study(),study('differt')
    b['records'].append(copy.deepcopy(b['records'][0]))
    b['records'][1]['tx']='TX'
    with pytest.raises(ValueError,match='Ambiguous'):c.compare_studies(a,b)


def test_missing_configuration_cannot_be_called_verified():
    a,b=study(),study('differt')
    for value in (a,b):value['context'].pop('antenna/rx/polarization')
    assert c.compare_studies(a,b)['pairs'][0]['status']=='partially_verified'


def test_html_escapes_names_and_exports_snapshots(tmp_path):
    a,b=study(),study('differt')
    a['records'][0]['tx']=b['records'][0]['tx']='<script>alert(1)</script>'
    path,report=c.write_report(tmp_path,a,b)
    assert '<script>alert(1)</script>' not in path.read_text(encoding='utf-8')
    assert c.load_study(tmp_path/'sionna.study.json')['run_id']=='sionna'
    assert (tmp_path/'comparison.csv').is_file()


def test_geometry_fingerprint_is_name_independent_and_material_sensitive(tmp_path):
    (tmp_path/'a.ply').write_bytes(b'ply\nformat ascii 1.0\ncomment Sionna exporter\nend_header\nidentical vertices and faces')
    def config(material):
        (tmp_path/'scene.xml').write_text('<scene><shape type="ply"><string name="filename" value="a.ply"/><ref id="mat-prefix"/></shape></scene>')
        return {'scene_xml':str(tmp_path/'scene.xml'),'frames':[{'frame':1,'materials':[{'source_name':'prefix','blender_name':material}]}]}
    first=c.geometry_evidence(config('concrete'))['1']['sha256']
    assert first
    (tmp_path/'a.ply').write_bytes(b'ply\nformat ascii 1.0\ncomment DiffeRT exporter\nend_header\nidentical vertices and faces')
    assert c.geometry_evidence(config('concrete'))['1']['sha256']==first
    assert c.geometry_evidence(config('glass'))['1']['sha256']!=first
