import copy
import json
import math
import pytest
from test_comparison import study,c
import path_diagnostics as d


def traced(engine='sionna', paths=None, expected=None):
    value=study(engine)
    value['path_coefficient_convention']='passband_without_propagation_phase'
    paths=paths if paths is not None else [path()]
    expected=len(paths) if expected is None else expected
    value['records'][0]['metrics']['path_count']=expected
    link=dict(frame=1,pair=0,tx=value['records'][0]['tx'],rx=value['records'][0]['rx'],
              paths=paths,expected_paths=expected,captured_paths=len(paths),
              coverage='complete' if expected==len(paths) else 'subset',issues=[])
    value['path_traces']=dict(run_id=value['run_id'],source='test',links=[link])
    return value


def path(index=0,x=0,gain=-60):
    return dict(path_index=index,points=[[-2,0,1],[x,0,0],[2,0,1]],interactions=[1],
                path_gain_db=gain,delay_ns=15.,phase_rad=math.pi-.01,doppler_hz=0.)


def compare(a,b,**kw):return d.compare(a,b,c.compare_studies(a,b),**kw)


def test_match_geometry_not_id_order_or_gain():
    a=traced(paths=[path(1,0),path(2,1)])
    b=traced('differt',paths=[path(99,1,-61),path(98,.0001,-62)])
    result=compare(a,b)
    assert result['counts']=={'matched':2}
    assert result['rows'][0]['differt']['path_index']==98
    assert result['rows'][0]['delta_path_gain_db']==-2
    assert result['rows'][0]['max_vertex_error_m']==pytest.approx(.0001)


def test_interaction_sequence_and_tolerance():
    a,b=traced(),traced('differt',paths=[path(x=.002)])
    assert compare(a,b)['counts']=={'differt_only':1,'sionna_only':1}
    assert compare(a,b,tolerance_m=.003)['counts']=={'matched':1}
    b['path_traces']['links'][0]['paths'][0]['interactions']=[8]
    assert 'matched' not in compare(a,b,tolerance_m=.003)['counts']


def test_ambiguous_duplicates_do_not_get_metric_deltas():
    a,b=traced(paths=[path(1),path(2)]),traced('differt')
    result=compare(a,b)
    assert result['counts']=={'ambiguous_match':1,'ambiguous_sionna':1}
    assert all(r['delta_path_gain_db'] is None for r in result['rows'])


def test_augmenting_match_finds_maximum_cardinality():
    # A0 can reach either B, while A1 can reach only B0.
    a=traced(paths=[path(1,0),path(2,-.0007)])
    b=traced('differt',paths=[path(8,-.0001),path(9,.0007)])
    result=compare(a,b,tolerance_m=.001)
    assert sum(bool(r['sionna'] and r['differt']) for r in result['rows'])==2
    assert result['counts']=={'ambiguous_match':2}


def test_subset_never_claims_only_in_engine():
    a=traced(paths=[path(1,1)],expected=3);b=traced('differt')
    assert compare(a,b)['counts']=={'differt_unmatched_subset':1,'sionna_unmatched_subset':1}


def test_unverified_or_stale_capture_not_compared():
    a,b=traced(),traced('differt')
    b['path_traces']['run_id']='wrong'
    assert compare(a,b)['links'][0]['diagnostics']=='traces_unavailable'
    b=traced('differt');b.pop('geometry_evidence')
    assert compare(a,b)['links'][0]['diagnostics']=='input_review_required'
    assert compare(a,b)['rows']==[]


def test_phase_wrap_and_budget_failure():
    a,b=traced(),traced('differt')
    b['path_traces']['links'][0]['paths'][0]['phase_rad']=-math.pi+.01
    assert compare(a,b)['rows'][0]['delta_phase_rad']==pytest.approx(.02)
    result=compare(a,b,budget=0)
    assert result['links'][0]['diagnostics']=='matching_unavailable' and not result['rows']
    with pytest.raises(ValueError,match='tolerance'):compare(a,b,tolerance_m=0)


def test_legacy_or_unknown_phase_is_not_silently_compared(tmp_path):
    a,b=traced(),traced('differt')
    b.pop('path_coefficient_convention');b['bridge_version']='0.5.0'
    result=d.write_report(tmp_path,a,b,c.compare_studies(a,b))
    assert not result['phase_comparable']
    assert result['rows'][0]['delta_phase_rad'] is None
    assert result['rows'][0]['delta_path_gain_db']==0
    assert 'coefficient conventions differ or are unknown' in (tmp_path/'path_diagnostics.html').read_text(encoding='utf-8')
    b['bridge_version']=''
    assert compare(a,b)['phase_conventions']['differt']=='unknown'


def columns():
    return dict(frame=[1]*3,pos_idx=[0]*3,path_index=[4]*3,point_order=[0,1,2],
                point_role_id=[1,2,3],interaction_id=[0,1,0],num_events=[1]*3,
                x=[-2,0,2],y=[0]*3,z=[1,0,1],path_gain_db=[-60]*3,delay_ns=[15]*3)


def test_saved_attribute_reconstruction_and_empty_links():
    a=study();result=d.from_columns(a,columns())
    assert result['links'][0]['coverage']=='complete'
    assert result['links'][0]['paths'][0]['points']==[[-2,0,1],[0,0,0],[2,0,1]]
    a['records'][0]['metrics']['path_count']=0
    assert d.from_columns(a,{k:[] for k in d.REQUIRED_COLUMNS})['links'][0]['coverage']=='complete'


def test_missing_corrupt_and_limited_attributes():
    a=study();cols=columns();cols.pop('point_order')
    assert d.from_columns(a,cols)['source']=='unavailable'
    cols=columns();cols['point_order']=[0,1,1]
    result=d.from_columns(a,cols)
    assert result['links'][0]['coverage']=='incomplete' and not result['links'][0]['paths']
    result=d.from_columns(a,columns(),max_paths=0)
    assert result['links'][0]['coverage']=='incomplete'


def test_html_names_and_json_are_safe(tmp_path):
    a,b=traced(),traced('differt')
    label='</script><img src=x onerror=alert(1)>__ROWS__'
    # Update both link identities and captured input keys, keeping the source complete.
    for value in (a,b):
        old=value['records'][0]['tx'];value['records'][0]['tx']=label
        values=value['records'][0]['values']
        value['records'][0]['values']={k.replace('/'+old+'/', '/'+label+'/'):v for k,v in values.items()}
        value['path_traces']['links'][0]['tx']=label
    c.write_report(tmp_path,a,b)
    page=(tmp_path/'path_diagnostics.html').read_text(encoding='utf-8')
    assert label not in page and '&lt;/script&gt;' in page
    assert '\\u003c/script\\u003e' in page
    assert json.loads((tmp_path/'sionna.study.json').read_text())['path_traces']['links']
