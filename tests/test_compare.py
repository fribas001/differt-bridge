import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('compare',Path(__file__).resolve().parents[1]/'scripts/compare_runs.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

def test_comparison_keeps_missing_links_and_flags_settings():
    a={(1,0):({'tx_name':'TX','total_power_db':-60.}, {'frequency_hz':3e9}),(2,0):({'path_count':0},{})}
    b={(1,0):({'tx_name':'DiffeRT_TX','total_power_db':-62.},{'frequency_hz':4e9})}
    rows=c.compare(a,b)
    gain=next(r for r in rows if r['frame']==1 and r['metric']=='total_power_db')
    assert gain['differt_minus_sionna']==-2.
    assert gain['status']=='settings_differ'
    assert all(r['status']=='missing_link' for r in rows if r['frame']==2)
