import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/differt_bridge'))
import benchmark as b
import comparison
from test_comparison import study


def captured(tmp_path, *, seed=42, paths=1, gain=-60):
    studies=[]
    for engine in b.ENGINES:
        s=study(engine,gain,paths)
        s['records'][0]['values']['solver/seed']=seed
        s['execution']={'wall_seconds_including_export_import':10 if engine=='sionna' else 20}
        studies.append(s)
    comparison.write_report(tmp_path,*studies)
    return b.collect(tmp_path,b.plan(1,1,1,42)[0],{},1)


def test_plan_is_bounded_and_alternates_per_depth():
    p=b.plan(0,2,3,42,True)
    assert len(p)==9 and [r['seed'] for r in p]==[42]*3+[43]*3+[44]*3
    for depth in range(3):
        group=[r for r in p if r['depth']==depth]
        assert group[0]['engine_order']==group[2]['engine_order']
        assert group[0]['engine_order']==list(reversed(group[1]['engine_order']))
    for args in [(2,1,3,42),(0,7,1,42),(0,6,10,42),(0,1,0,42),(1,1,1,-1),(1.,1,1,42)]:
        with pytest.raises(ValueError):b.plan(*args)
    with pytest.raises(ValueError):b.plan(1,1,2,2147483647,True)


def test_capture_and_input_drift(tmp_path):
    run=captured(tmp_path)
    assert run['eligible'] and run['path_totals']==dict(sionna=1,differt=1)
    same=b.collect(tmp_path,b.plan(1,1,1,42)[0],run['signatures'],1)
    assert same['eligible']
    path=tmp_path/'differt.study.json';data=json.loads(path.read_text())
    data['records'][0]['values']['solver/differt_chunk_size']=128
    path.write_text(json.dumps(data))
    changed=b.collect(tmp_path,b.plan(1,1,1,42)[0],run['signatures'],1)
    assert not changed['eligible'] and 'non-sweep' in changed['issues'][0]


def test_plan_disagreement_cannot_be_silently_aggregated(tmp_path):
    run=captured(tmp_path,seed=43)
    assert not run['eligible'] and any('captured frame/depth/seed' in i for i in run['issues'])
    assert b.summarize([run])[0]['engines']['sionna']['time_seconds']['n']==0


def test_signature_excludes_only_planned_inputs():
    a=study();a['records'][0]['values']['solver/seed']=42
    c=copy.deepcopy(a);c['records'][0]['values']['solver/seed']=43;c['records'][0]['values']['solver/max_depth']=2
    assert b.fingerprint(a)==b.fingerprint(c)
    c['geometry_evidence']['1']['sha256']='edited'
    assert b.fingerprint(a)!=b.fingerprint(c)


def test_no_path_values_and_single_repeat_stay_unavailable(tmp_path):
    run=captured(tmp_path,paths=0)
    assert run['eligible'] and run['max_absolute_gain_delta_db'] is None
    assert run['no_path_links']==dict(sionna=1,differt=1)
    for engine in b.summarize([run])[0]['engines'].values():
        assert engine['max_gain_span_db'] is None
        assert engine['links_with_changing_path_count'] is None


def test_repeat_variability_and_exclusion(tmp_path):
    a=captured(tmp_path/'a');c=captured(tmp_path/'c',gain=-59,paths=2)
    excluded=copy.deepcopy(c);excluded['eligible']=False;excluded['timing_seconds']['sionna']=1e9
    summary=b.summarize([a,c,excluded])[0]
    assert summary['eligible']==2
    assert summary['engines']['sionna']['max_gain_span_db']==1
    assert summary['engines']['sionna']['links_with_changing_path_count']==1
    assert summary['engines']['sionna']['time_seconds']==dict(n=2,median=10,minimum=10,maximum=10)


def test_partial_checkpoint_and_html_escape(tmp_path):
    run=captured(tmp_path/'run');run['report']='run/comparison.html'
    doc=dict(status='Cancelled',message='<script>oops</script>',plan=b.plan(1,2,3,42),runs=[run],environment={'scene':'<hello>'})
    b.write_report(tmp_path,doc)
    page=(tmp_path/'benchmark.html').read_text()
    assert '<script>oops</script>' not in page and '&lt;script&gt;oops' in page
    assert '1 / 6 paired runs' in page
    assert json.loads((tmp_path/'benchmark.json').read_text())['status']=='Cancelled'
    assert (tmp_path/'benchmark.csv').read_text().count('\n')==2


def test_unavailable_timing_excluded(tmp_path):
    captured(tmp_path)
    path=tmp_path/'point_coverage.json';data=json.loads(path.read_text());data['execution']['sionna']={}
    path.write_text(json.dumps(data))
    run=b.collect(tmp_path,b.plan(1,1,1,42)[0],{},1)
    assert not run['eligible'] and run['timing_seconds']['sionna'] is None
