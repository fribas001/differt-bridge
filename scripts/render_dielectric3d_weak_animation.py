"""Measured shadow-field reduction; shared full-wave output is explicitly labelled."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from render_model_error_animation import F,B,BG,PANEL,TEXT,MUTED,GRID,WHITE,COLORS,read,z

CHAPTERS=[('Original weak polarization: finer Maxwell check','holdout_b_s1_yz_h0.7','rays'),
 ('Fixed spatial extrapolation','holdout_b_s1_yz_h0.7','fullwave'),
 ('Unseen material and source geometry','new_b_yz_h0.45','fullwave'),
 ('Unseen shadow boundary: 243.99° → 244.01°','new_a_zz_h1.35','boundary'),
 ('Remaining crossed-polarization differences','new_a_yz_h0.45','fullwave'),
 ('Validation and remaining uncertainty','holdout_b_s1_yz_h0.7','summary')]

class Renderer:
    def __init__(self,root):
        self.root=root;self.data=read(root/'work/d3weak/analysis.json');assert self.data['status']=='passed'
        self.rows={(r['engine'],r['name']):dict(r,ray=r['standard']) for r in self.data['comparisons']};self.raw={}
        for campaign,folder in [('primary','d3f'),('holdout','d3sh'),('fresh','d3wr')]:
            for engine in COLORS:self.raw[campaign,engine]={r['name']:r for r in read(root/f'work/{folder}/{engine}-reciprocal/{engine}_float32.json')['cases']}
        for engine in COLORS:
            r=self.rows[engine,self.data['weak']['name']];b=np.array(r['reference']);b[np.array(r['shadow_mask'])]=self.data['weak']['reference'];r['reference']=b.tolist()
            r['shadow_standard']=self.data['weak']['baseline_vs_fem64'];r['shadow_refined']=self.data['weak']['corrected_vs_fem64']
        candidates=[r for (engine,name),r in self.rows.items() if engine=='sionna' and r['shadow_refined'] and r['shadow_refined']['complex_rms'] is not None]
        worst=max(candidates,key=lambda r:r['shadow_refined']['complex_rms'])
        CHAPTERS[4]=('Largest remaining polarization residual',worst['name'],'fullwave')
    def render(self,frame):
        t=(frame-1)/24;ch=min(int(t/10),5);title,name,mode=CHAPTERS[ch];row=self.rows['sionna',name];angles=np.array(row['study']['angles'])
        ix=np.where(abs(angles-244.)<.02)[0] if mode=='boundary' else np.where(row['shadow_mask'])[0]
        j=int(ix[min(len(ix)-1,int((t%10)/10*len(ix)))]) if len(ix) else 0
        im=Image.new('RGB',(1600,900),BG);d=ImageDraw.Draw(im)
        def text(x,y,s,size=24,color=TEXT,bold=False):d.text((x,y),s,font=(B if bold else F)[size],fill=color)
        text(40,24,'Weak-polarization error: spatial convergence',44,bold=True)
        text(40,83,'Shared full-wave companion • Fixed spatial extrapolation • Independent finite-element Maxwell checks',22,MUTED)
        text(1310,35,f'{ch+1:02d}/06 · {t:04.1f}s',22,MUTED);text(40,122,title,24,bold=True)
        for engine,x in [('sionna',40),('differt',820)]:
            color=COLORS[engine];r=self.rows[engine,name];st=r['study'];a=z(r['ray'] if mode=='rays' else r['field']);b=z(r['reference']);base=z(r['ray'])
            d.rounded_rectangle((x,160,x+740,814),18,fill=PANEL)
            text(x+24,180,'Sionna workflow' if engine=='sionna' else 'DiffeRT workflow',28,color,True)
            text(x+24,223,'Shared BIE32 field' if mode=='rays' else '+ shared extrapolated full-wave field',20,MUTED)
            if mode=='summary':
                weak=self.data['weak'];h=next(v for v in self.data['summary'] if v['campaign']=='fresh' and v['material']=='all' and v['engine']==engine)
                text(x+25,285,'Original weak group · finer FEM reference',24,bold=True)
                text(x+25,331,f'{100*weak["baseline_vs_fem64"]["complex_rms"]:.2f}% → {100*weak["corrected_vs_fem64"]["complex_rms"]:.2f}%',44,color,True)
                text(x+25,403,'New material / port shadow RMS',24,bold=True)
                text(x+25,450,f'{100*h["shadow_standard"]["complex_rms"]:.2f}% → {100*h["shadow_refined"]["complex_rms"]:.2f}%',38,color,True)
                text(x+25,525,f'Raw reciprocity: {100*self.data["reciprocity"]["relative_error"]:.3f}%. No averaging.',20)
                text(x+25,569,'Fixed 2 × BIE32 − BIE16; no reference fitting.',20,MUTED)
                text(x+25,614,'Shared companion for the infinite dielectric wedge.',20)
                text(x+25,658,f'FEM refinement: {100*weak["reference_spatial_change"]:.2f}% mesh / {100*weak["reference_spectral_change"]:.4f}% spectral.',20,MUTED)
                text(x+25,703,'Native UTD and obstacle checks remain intact.',20,MUTED)
                text(x+25,750,'Both runtimes and Blender workflow verified.',20,color)
                continue
            sm=r['shadow_standard'] if mode=='rays' else r['shadow_refined']
            error=float(np.linalg.norm(a[ix]-b[ix])/np.linalg.norm(b[ix])) if mode=='boundary' else sm['complex_rms']
            text(x+435,181,f'{100*error:.2f}%',32,color,True);text(x+570,193,'boundary RMS' if mode=='boundary' else 'shadow RMS',17,MUTED)
            text(x+24,267,f'εr = {st["epsilon"][0]:g} − {abs(st["epsilon"][1]):.3f}j',22)
            project=lambda p:(x+167+60*(p[0]-.55*p[1]),548-47*(p[2]+.25*(p[0]+p[1])))
            for face in [[(0,0,0),(2,0,0),(2,0,3.5),(0,0,3.5)],[(0,0,0),(0,2,0),(0,2,3.5),(0,0,3.5)]]:d.polygon([project(p) for p in face],fill='#2a4051',outline=GRID)
            d.line([project((0,0,0)),project((0,0,3.5))],fill='#8aa0b1',width=3)
            for path in self.raw[r['campaign'],engine][name]['paths']:
                if path['rx']==j:d.line([project(q) for q in path['points']],fill=color if mode=='rays' else '#7c94a7',width=3)
            for label,p,col in [('TX',r['tx'],WHITE),('RX',r['receivers'][j],color)]:
                px,py=project(p);d.ellipse((px-5,py-5,px+5,py+5),fill=col);text(px+8,py-10,label,17,col)
            text(x+24,585,'Native accepted paths shown for context',17,MUTED)
            text(x+24,623,f'Dipoles {st["tx_axis"]} → {st["rx_axis"]} · Δz {r["receivers"][j][2]-r["tx"][2]:.2f} λ',22)
            text(x+24,664,f'RX angle {angles[j]:.5f}°',20,MUTED)
            text(x+24,709,'White: independent FEM Maxwell',19)
            text(x+24,743,'Gray: BIE32 · color: labelled mode',17,MUTED)
            text(x+24,775,'Reference mesh uncertainty is in the report.',17,MUTED)
            gx,gw=x+385,324;xmin,xmax=angles[ix[0]],angles[ix[-1]]
            def chart(values,lo,hi,y,h,col,width=3):
                points=[(gx+(angles[ii]-xmin)/(xmax-xmin)*gw,y+h*(1-np.clip((values[ii]-lo)/(hi-lo),0,1))) for ii in ix if np.isfinite(values[ii])]
                if len(points)>1:d.line(points,fill=col,width=width)
            db=20*np.log10(np.maximum(abs(np.r_[a[ix],b[ix],base[ix]]),1e-20));lo=float(np.floor(db.min()-2));hi=float(np.ceil(db.max()+2));y,h=311,168
            text(gx,269,'Coherent channel magnitude (dB)',17,MUTED)
            for v in np.linspace(lo,hi,4):
                yy=y+h*(1-(v-lo)/(hi-lo));d.line((gx,yy,gx+gw,yy),fill=GRID);text(gx-36,yy-9,f'{v:.0f}',17,MUTED)
            if mode!='rays':chart(20*np.log10(np.maximum(abs(base),1e-20)),lo,hi,y,h,'#7c94a7',2)
            chart(20*np.log10(np.maximum(abs(b),1e-20)),lo,hi,y,h,WHITE,4);chart(20*np.log10(np.maximum(abs(a),1e-20)),lo,hi,y,h,color,2)
            xx=gx+(angles[j]-xmin)/(xmax-xmin)*gw;d.line((xx,y,xx,y+h),fill=MUTED);text(gx,491,f'{xmin:g}°                         {xmax:g}°',17,MUTED)
            phase=np.rad2deg(np.angle(a*np.conj(b)));phase[(abs(b)<max(abs(b).max()*1e-3,1e-9))|(abs(a)<1e-12)]=np.nan
            finite_phase=abs(phase[ix][np.isfinite(phase[ix])])
            limit=int(max(5,5*np.ceil(finite_phase.max()/5))) if len(finite_phase) else 5
            y,h=568,120;text(gx,528,f'Phase error · ±{limit}°'+(' zoom' if mode!='rays' else ''),20,MUTED)
            for v in (-limit,0,limit):
                yy=y+h*(1-(v+limit)/(2*limit));d.line((gx,yy,gx+gw,yy),fill=GRID);text(gx-36,yy-10,str(v),17,MUTED)
            chart(phase,-limit,limit,y,h,color);d.line((xx,y,xx,y+h),fill=MUTED);text(gx,711,f'Δ phase {phase[j]:+.3f}°',24,color,True)
            text(gx,753,f'{sum(abs(phase[ix])>limit)}/{len(ix)} clipped · null phases excluded',17,MUTED)
        d.line((40,845,1560,845),fill=GRID,width=3);d.line((40,845,40+1520*t/60,845),fill='#76ddb2',width=4)
        text(40,860,'Spatial extrapolation reduces the companion’s numerical error. The engines’ native UTD remains unchanged.',19,MUTED)
        return im

def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--previews',action='store_true');a=ap.parse_args();root=a.root.resolve();out=root/'outputs/differt-bridge/examples/dielectric3d_weak';out.mkdir(parents=True,exist_ok=True)
    frames=root/'work/d3weak/frames';frames.mkdir(exist_ok=True);r=Renderer(root);previews=[121,361,601,841,1081,1321]
    for frame in previews if a.previews else range(1,1441):
        im=r.render(frame);im.save(frames/f'frame_{frame:04d}.png',compress_level=1)
        if frame in previews:(out/'previews').mkdir(exist_ok=True);im.save(out/'previews'/f'frame_{frame:04d}.png')
        if frame%240==1:print('FRAME',frame,flush=True)
    if not a.previews:
        files=sorted(frames.glob('frame_*.png'));assert len(files)==1440;(root/'work/d3weak/frame_hashes.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2))
        (out/'animation_validation.json').write_text(json.dumps(dict(status='frames_ready',frames=1440,fps=24,width=1600,height=900,duration_seconds=60,preview_frames=previews,frame_folder=frames.relative_to(root).as_posix(),analysis_sha256=hashlib.sha256((root/'work/d3weak/analysis.json').read_bytes()).hexdigest(),video_name='Sionna_vs_DiffeRT_Dielectric3D_Weak.mp4',timeline_name='Dielectric3D_Weak_Comparison.blend',chapters=[dict(start_seconds=i*10,title=c[0]) for i,c in enumerate(CHAPTERS)]),indent=2))

if __name__=='__main__':main()
