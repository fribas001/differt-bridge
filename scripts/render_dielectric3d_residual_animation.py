"""Measured fields and explicit reference convergence, with unchanged workflows."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from render_model_error_animation import font,BG,PANEL,TEXT,MUTED,GRID,WHITE,COLORS,read,z
F={s:font(s) for s in (16,17,18,19,20,22,24,26,28,32,38,44)}
B={s:font(s,True) for s in F}

CHAPTERS=[('Previous 1.56% residual · FEM96/64 reference','holdout_b_s0_zx_h0.7','previous'),
 ('Further independent Maxwell refinement','holdout_b_s0_zx_h0.7','current'),
 ('Finer boundary-integral candidate · research only','holdout_b_s0_zx_h0.7','candidate'),
 ('Spatial convergence with production field fixed','holdout_b_s0_zx_h0.7','convergence'),
 ('Shadow boundary · same geometry and material','holdout_b_s0_zx_h0.7','boundary'),
 ('Validated results and remaining uncertainty','holdout_b_s0_zx_h0.7','summary')]

class Renderer:
    def __init__(self,root):
        self.root=root;self.a=read(root/'work/d3res/analysis.json');assert self.a['status']=='passed'
        out=root/'outputs/differt-bridge/examples/dielectric3d_residual'
        for name in ('native_workflow_health.json','reciprocal_blender.json'):assert read(out/name)['status']=='passed'
        assert read(root/'work/d3res/rays/receipt.json')['status']=='passed'
        assert read(root/'work/d3res/workflow/comparison.json')['status']=='passed'
        self.rows={(r['engine'],r['name']):r for r in self.a['comparisons']}
        self.raw={e:{r['name']:r for r in read(root/f'work/d3res/rays/{e}-reciprocal/{e}_float32.json')['cases']} for e in COLORS}
    def render(self,frame):
        t=(frame-1)/24;ch=min(int(t/10),5);title,name,mode=CHAPTERS[ch]
        im=Image.new('RGB',(1600,900),BG);d=ImageDraw.Draw(im)
        def text(x,y,s,size=24,color=TEXT,bold=False):d.text((x,y),s,font=(B if bold else F)[size],fill=color)
        text(40,22,'Remaining polarization residual: independent refinement',38,bold=True)
        text(40,77,'Production companion • Finer BIE candidate • Independent volume FEM • Both workflows preserved',22,MUTED)
        text(1360,27,f'{ch+1:02d}/06 · {t:04.1f}s',20,MUTED);text(40,118,title,26,bold=True)
        for engine,x in [('sionna',40),('differt',820)]:
            color=COLORS[engine];r=self.rows[engine,name];angles=np.array(r['study']['angles']);mask=np.array(r['shadow_mask'])
            ix=np.where(abs(angles-223.5)<.02)[0] if mode=='boundary' else np.where(mask)[0]
            j=ix[min(len(ix)-1,int((t%10)/10*len(ix)))];p=z(r['candidate'] if mode=='candidate' else r['field']);old=z(r['previous_reference']);ref=old if mode=='previous' else z(r['reference'])
            d.rounded_rectangle((x,158,x+740,815),18,fill=PANEL)
            text(x+24,178,('Sionna' if engine=='sionna' else 'DiffeRT')+' workflow',28,color,True)
            text(x+24,220,'+ research BIE32/64 candidate' if mode=='candidate' else '+ production BIE16/32 companion',20,MUTED)
            if mode=='summary':
                levels=self.a['target']['series'];first=next(v for v in levels if v['resolution']==96);last=levels[-1]
                text(x+24,279,'Target disagreement as reference is refined',24,bold=True)
                text(x+24,325,f'{100*first["companion"]["complex_rms"]:.2f}% → {100*last["companion"]["complex_rms"]:.2f}%',44,color,True)
                text(x+24,400,'Final reference increment (112 → 128, q < 7)',22)
                text(x+24,445,f'{100*last["mesh_change"]["complex_rms"]:.3f}% · sensitivity, not an error bound',24,color)
                text(x+24,511,f'Research BIE32/64 candidate: {100*last["candidate"]["complex_rms"]:.2f}%',24)
                text(x+24,559,'Candidate tested on one material; default is unchanged.',19,MUTED)
                text(x+24,608,'No gain fitting, phase fitting or channel switching.',20)
                text(x+24,655,'FEM128 below q=7; audited FEM64 tail retained.',20,MUTED)
                text(x+24,701,'Infinite dielectric wedge · single-frequency field.',20,MUTED)
                text(x+24,751,'Both runtimes and Blender workflows verified.',20,color)
                continue
            if mode=='convergence':
                text(x+24,273,'Same field, five independently resolved meshes',24,bold=True)
                levels=self.a['target']['series'][-5:];values=np.array([v['companion']['complex_rms']*100 for v in levels]);maximum=max(values)*1.15
                gx,gy,gw,gh=x+70,340,600,290
                for tick in np.linspace(0,maximum,5):
                    yy=gy+gh*(1-tick/maximum);d.line((gx,yy,gx+gw,yy),fill=GRID);text(gx-46,yy-10,f'{tick:.1f}%',17,MUTED)
                pts=[(gx+30+i*(gw-60)/4,gy+gh*(1-v/maximum)) for i,v in enumerate(values)]
                d.line(pts,fill=color,width=4)
                active=min(4,int((t%10)/2))
                for i,((xx,yy),v) in enumerate(zip(pts,levels)):
                    d.ellipse((xx-5,yy-5,xx+5,yy+5),fill=WHITE if i==active else color);text(xx-22,gy+gh+12,str(v['resolution']),20,MUTED);text(xx-31,yy-35,f'{values[i]:.2f}%',20,color)
                text(x+24,691,'Spatial resolution in cells per vacuum wavelength',20,MUTED)
                text(x+24,733,'80–128 refine q < 7; high-q tail stays at 64.',20,MUTED)
                text(x+24,773,'Companion output is identical at every point above.',18)
                continue
            error=np.linalg.norm((p-ref)[ix])/np.linalg.norm(ref[ix])
            text(x+455,179,f'{100*error:.2f}%',32,color,True);text(x+580,190,'boundary RMS' if mode=='boundary' else 'shadow RMS',16,MUTED)
            text(x+24,263,f'εr ≈ {r["study"]["epsilon"][0]:g} − {abs(r["study"]["epsilon"][1]):g}i',22)
            project=lambda q:(x+155+61*(q[0]-.55*q[1]),540-48*(q[2]+.25*(q[0]+q[1])))
            for face in [[(0,0,0),(2,0,0),(2,0,3.5),(0,0,3.5)],[(0,0,0),(0,2,0),(0,2,3.5),(0,0,3.5)]]:d.polygon([project(q) for q in face],fill='#2a4051',outline=GRID)
            for path in self.raw[engine][name]['paths']:
                if path['rx']==j:d.line([project(q) for q in path['points']],fill='#7c94a7',width=3)
            for label,q,col in [('TX',r['tx'],WHITE),('RX',r['receivers'][j],color)]:
                xx,yy=project(q);d.ellipse((xx-5,yy-5,xx+5,yy+5),fill=col);text(xx+8,yy-10,label,17,col)
            text(x+24,580,'Engine paths shown for context',17,MUTED)
            text(x+24,619,'Dipoles z → x · wedge angle φ',22)
            text(x+24,657,f'{angles[j]:.5f}°',26,color,True)
            text(x+24,704,'Color: research BIE32/64' if mode=='candidate' else 'Color: production companion',19)
            text(x+24,739,'White: selected Maxwell reference',18)
            text(x+24,774,'Gray: previous FEM96/64',18,MUTED)
            gx,gw=x+385,320;xmin,xmax=angles[ix[0]],angles[ix[-1]]
            def chart(v,lo,hi,y,h,col,width=3):
                pts=[(gx+(angles[k]-xmin)/(xmax-xmin)*gw,y+h*(1-(v[k]-lo)/(hi-lo))) for k in ix if np.isfinite(v[k])]
                if len(pts)>1:d.line(pts,fill=col,width=width)
            db=lambda v:20*np.log10(np.maximum(abs(v),1e-20));bounds=np.r_[db(p)[ix],db(ref)[ix],db(old)[ix]];lo=np.floor(bounds.min()-1);hi=np.ceil(bounds.max()+1);y,h=318,160
            text(gx,274,'Coherent channel magnitude (dB)',17,MUTED)
            for v in np.linspace(lo,hi,4):
                yy=y+h*(1-(v-lo)/(hi-lo));d.line((gx,yy,gx+gw,yy),fill=GRID);text(gx-38,yy-10,f'{v:.0f}',17,MUTED)
            chart(db(old),lo,hi,y,h,'#7c94a7',4);chart(db(ref),lo,hi,y,h,WHITE,4);chart(db(p),lo,hi,y,h,color,2)
            xx=gx+(angles[j]-xmin)/(xmax-xmin)*gw;d.line((xx,y,xx,y+h),fill=MUTED)
            text(gx,488,f'{xmin:g}°',17,MUTED);right_label=f'{xmax:g}°';text(gx+gw-d.textlength(right_label,font=F[17]),488,right_label,17,MUTED)
            phase=np.rad2deg(np.angle(p*np.conj(ref)));phase[(abs(ref)<=max(abs(ref).max()*1e-3,1e-9))|(abs(p)<=max(abs(ref).max()*1e-5,1e-12))]=np.nan
            finite=abs(phase[ix][np.isfinite(phase[ix])]);limit=max(1,int(np.ceil(finite.max()))) if len(finite) else 1;y,h=567,120
            text(gx,528,f'Phase difference · ±{limit}°',20,MUTED)
            for v in (-limit,0,limit):
                yy=y+h*(1-(v+limit)/(2*limit));d.line((gx,yy,gx+gw,yy),fill=GRID);text(gx-35,yy-10,str(v),17,MUTED)
            chart(phase,-limit,limit,y,h,color);d.line((xx,y,xx,y+h),fill=MUTED);text(gx,711,f'Δ phase {phase[j]:+.3f}°',24,color,True)
            text(gx,753,'Previous FEM96 / FEM64 tail' if mode=='previous' else 'FEM128 q<7 / FEM64 tail',17,MUTED)
            text(gx,780,'No clipped samples · null phases excluded',16,MUTED)
        d.line((40,844,1560,844),fill=GRID,width=3);d.line((40,844,40+1520*t/60,844),fill='#76ddb2',width=4)
        text(40,858,'Default fields stay fixed. The finer BIE candidate is separate from both native ray tracers.',20,MUTED)
        return im

def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--previews',action='store_true');a=ap.parse_args();root=a.root.resolve();out=root/'outputs/differt-bridge/examples/dielectric3d_residual';out.mkdir(parents=True,exist_ok=True);frames=root/'work/d3res/frames';frames.mkdir(exist_ok=True)
    renderer=Renderer(root);previews=[121,361,601,841,1081,1321]
    for frame in previews if a.previews else range(1,1441):
        im=renderer.render(frame);im.save(frames/f'frame_{frame:04d}.png',compress_level=1)
        if frame in previews:(out/'previews').mkdir(exist_ok=True);im.save(out/'previews'/f'frame_{frame:04d}.png')
        if frame%240==1:print('FRAME',frame,flush=True)
    if not a.previews:
        files=sorted(frames.glob('frame_*.png'));assert len(files)==1440
        (root/'work/d3res/frame_hashes.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2))
        (out/'animation_validation.json').write_text(json.dumps(dict(status='frames_ready',frames=1440,fps=24,width=1600,height=900,duration_seconds=60,preview_frames=previews,frame_folder=frames.relative_to(root).as_posix(),analysis_sha256=hashlib.sha256((root/'work/d3res/analysis.json').read_bytes()).hexdigest(),video_name='Sionna_vs_DiffeRT_Residual.mp4',timeline_name='Dielectric3D_Residual_Comparison.blend',chapters=[dict(start_seconds=i*10,title=c[0]) for i,c in enumerate(CHAPTERS)]),indent=2))

if __name__=='__main__':main()
