"""Independent Maxwell samples at and on both sides of three GO boundaries."""
import json,sys
from pathlib import Path
import numpy as np
import run_maxwell_reference as campaign

campaign.SOURCES=np.array([[-1.5,2.5],[2.5,-1.5]])
receivers=[]
for point in ([1.8,-3.],[-1.8,-3.],[-3.,-1.8]):
    for angle in (-1e-5,0.,1e-5):
        c,s=np.cos(angle),np.sin(angle);receivers.append(np.array([[c,-s],[s,c]])@point)
campaign.RECEIVERS=np.array(receivers)
campaign.MATERIALS={'concrete':campaign.MATERIALS['concrete']}

if __name__=='__main__':
    if sys.argv[1]=='--manifest':
        import maxwell_engine_cases as fixtures
        fixtures.SOURCES=campaign.SOURCES;fixtures.RECEIVERS=campaign.RECEIVERS;fixtures.MATERIALS=campaign.MATERIALS
        Path(sys.argv[2]).write_text(json.dumps(dict(cases=fixtures.cases()),indent=2))
    else:campaign.main()
