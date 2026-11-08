"""Measure raw forward/reverse full-wave shadow dyads, without projection."""
import json,sys
from pathlib import Path
import numpy as np
from analyze_dielectric3d import read,z,pairs,rel

def main(root):
    work=root/'work/d3shadow';cases=read(work/'reciprocity_cases.json')['cases'];product=read(work/'reciprocity_standard_product.json');values={r['name']:z(r['field'])[0] for r in product['results']}
    f=np.zeros((3,3),complex);r=np.zeros((3,3),complex)
    for c in cases:
        s=c['study'];a=r if 'reverse_of' in s else f;a['xyz'.index(s['rx_axis']),'xyz'.index(s['tx_axis'])]=values[c['name']]
    ref=read(work/'concrete_fem64/result.json');ports=ref['ports'];first=next(c for c in cases if 'reverse_of' not in c['study']);si=ports['sources'].index(first['tx']);ri=ports['receivers'].index(first['receivers'][0]);b=z(ref['field'])[ri,:,si*3:si*3+3]
    error=rel(f,r.T);result=dict(status='passed' if error<.05 else 'failed',panels=product['panels'],forward=pairs(f),reverse=pairs(r),reference_forward=pairs(b),relative_reciprocity_error=error,forward_reference_rms=rel(f,b),reverse_reference_rms=rel(r,b.T),scope='Independent source-location BIE solves; no averaging. Reverse expected dyad follows the exact Lorentz transpose law from the independent forward FEM solution. The FEM reverse field was not separately solved at this pair.',gate='Raw reciprocity discrepancy below 5%, consistent with the declared optional-field tolerance; not an exact discrete reciprocity claim.')
    (work/'reciprocity_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k not in ('forward','reverse','reference_forward')}))
    if result['status']!='passed':raise SystemExit('Shadow reciprocity needs further refinement')

if __name__=='__main__':main(Path(sys.argv[1]).resolve())
