import copy
import csv
import json
import pytest
from test_comparison import study, c
from point_coverage import grid_positions, samples


def test_cell_centers_and_bounds():
    assert grid_positions((0,0,1.5), (4,2), 2,2) == [(-1,-.5,1.5),(1,-.5,1.5),(-1,.5,1.5),(1,.5,1.5)]
    for args in [((0,0,1), (4,2), 32,32), ((0,0,float('nan')), (4,2), 2,2), ((0,0,1), (0,2), 2,2)]:
        with pytest.raises(ValueError): grid_positions(*args)


def test_spatial_deltas_require_verified_inputs():
    a,b=study(),study('differt',-61)
    p=samples(a,b,c.compare_studies(a,b))[0]
    assert p['delta_db']==-1 and p['plot_eligible']
    b['records'][0]['values']['device/receivers/DiffeRT_RX/position/0']=3
    p=samples(a,b,c.compare_studies(a,b))[0]
    assert p['delta_db'] is None and not p['plot_eligible']
    assert p['sionna_position']==[2,0,1] and p['differt_position']==[3,0,1]


def test_no_path_and_missing_link_points():
    a,b=study(paths=0),study('differt',-61)
    p=samples(a,b,c.compare_studies(a,b))[0]
    assert p['sionna_gain_db'] is None and p['delta_db'] is None
    assert p['plot_eligible'] and p['sionna_paths']==0
    b['records'][0]['rx']='Different'
    assert all(not p['plot_eligible'] for p in samples(a,b,c.compare_studies(a,b)))


def test_coverage_export_timing_and_unknown_coordinates(tmp_path):
    a,b=study(),study('differt')
    a['execution']={'wall_seconds_including_export_import':1.25}
    a['records'][0]['values'].pop('device/receivers/RX/position/0')
    c.write_report(tmp_path,a,b)
    data=json.loads((tmp_path/'point_coverage.json').read_text())
    assert data['execution']['sionna']==a['execution']
    assert not data['samples'][0]['plot_eligible']
    assert 'No verified receiver positions' in (tmp_path/'point_coverage.html').read_text(encoding='utf-8')
    with (tmp_path/'point_coverage.csv').open() as stream:
        row=next(csv.DictReader(stream)); assert row['delta_db']=='' and row['sionna_x']==''


def test_material_name_with_slash_is_checked():
    a,b=study(),study('differt')
    a['records'][0]['values']['material/Room/Wall/conductivity']=.1
    b['records'][0]['values']['material/Room/Wall/conductivity']=.2
    assert c.compare_studies(a,b)['pairs'][0]['status']=='inputs_differ'
