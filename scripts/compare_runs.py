"""Compare channel-link summaries from SionnaRT-Bridge and DiffeRT-Bridge.

python scripts/compare_runs.py sionna/frames_manifest.json differt/frames_manifest.json --output comparison.csv
"""
import argparse,csv,json,math,sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src/differt_bridge'))
import comparison

METRICS=('path_count','total_power_db','strongest_path_gain_db','first_arrival_ns',
         'mean_excess_delay_ns','rms_delay_spread_ns','rms_doppler_spread_hz','max_abs_doppler_hz')

def load(path):
    payload=json.loads(Path(path).read_text(encoding='utf-8'))
    frames=payload.get('frames') or [payload]
    result={}
    for frame in frames:
        analytics=frame.get('channel_analytics',{})
        if not analytics and frame.get('results_json'):
            source=Path(frame['results_json'])
            if not source.is_absolute():source=Path(path).parent/source
            analytics=json.loads(source.read_text(encoding='utf-8')).get('channel_analytics',{})
        for link in analytics.get('links',[]):
            key=(int(link.get('frame',frame.get('frame',0))),int(link['pos_idx']))
            if key in result:raise ValueError(f'Duplicate frame/link index {key}')
            result[key]=(link,frame.get('simulation',{}))
    if not result:raise ValueError(f'No channel link summaries found in {path}; choose a propagation-path manifest')
    return result

def compare(left,right):
    rows=[]
    for key in sorted(left.keys()|right.keys()):
        a,sa=left.get(key,({},{}));b,sb=right.get(key,({},{}))
        mismatch=[k for k in ('frequency_hz','max_depth','los','specular_reflection','diffuse_reflection','refraction','diffraction') if k in sa and k in sb and sa[k]!=sb[k]]
        for metric in METRICS:
            av,bv=a.get(metric),b.get(metric)
            delta=bv-av if isinstance(av,(float,int)) and isinstance(bv,(float,int)) and math.isfinite(av) and math.isfinite(bv) else None
            rows.append(dict(frame=key[0],pos_idx=key[1],sionna_tx=a.get('tx_name',''),differt_tx=b.get('tx_name',''),
                sionna_rx=a.get('rx_name',''),differt_rx=b.get('rx_name',''),metric=metric,sionna=av,differt=bv,
                differt_minus_sionna=delta,status='missing_link' if not a or not b else 'settings_differ' if mismatch else 'matched_index',
                differing_settings=','.join(mismatch)))
    return rows

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sionna');parser.add_argument('differt');parser.add_argument('--output',type=Path,default=Path('comparison.csv'))
    parser.add_argument('--report-dir',type=Path,help='HTML/CSV/JSON report from HDF5, metadata JSON/ZIP or study snapshots')
    parser.add_argument('--path-tolerance-mm',type=float,default=1.,help='Maximum corresponding vertex separation for path matching (default 1 mm)')
    args=parser.parse_args()
    if args.report_dir:
        path, report = comparison.write_report(args.report_dir, comparison.load_study(args.sionna), comparison.load_study(args.differt), path_tolerance_m=args.path_tolerance_mm/1000.)
        print(f"{len(report['pairs'])} links compared: {path}")
        return
    rows=compare(load(args.sionna),load(args.differt))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(f'{len(rows)} metric rows written to {args.output}. Pairing is by frame and link index; verify endpoint names and geometry before drawing conclusions.')
if __name__=='__main__':main()
