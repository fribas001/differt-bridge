"""New film: engine-derived ray baseline beside an explicitly labelled 2D solve."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from render_model_error_animation import F,B,BG,PANEL,TEXT,MUTED,GRID,WHITE,COLORS
from analyze_model_errors import read,z

CHAPTERS=[(0,'Reciprocal ray model','concrete_Hz',4,False),(10,'Coupled Maxwell refinement','concrete_Hz',4,True),(20,'Vertical polarization','concrete_Ez',4,True),(30,'Lower-permittivity dielectric','holdout_low_Hz',4,True),(40,'Higher-permittivity dielectric','holdout_high_Hz',4,True),(50,'Validated improvement and limits','concrete_Hz',4,True)]

class Renderer:
    def __init__(self,root):
        self.root=root;self.data=read(root/'work/maxwell-refinement/analysis.json')
        self.groups={(r['profile'],r['name']):r for r in self.data['comparisons']}
        self.cases={c['name']:c for c in read(root/'work/mre/cases.json')['cases']}
        self.raw={e:{r['name']:r for r in read(root/f'work/mre/{e}-reciprocal/{e}_float32.json')['cases']} for e in COLORS}
    def render(self,frame):
        t=(frame-1)/24;ch=min(int(t//10),5);start,title,name,source,refined=CHAPTERS[ch];j=min(52,int((t-start)/10*53))
        im=Image.new('RGB',(1600,900),BG);d=ImageDraw.Draw(im)
        def text(x,y,s,size=24,c=TEXT,bold=False):d.text((x,y),s,font=(B if bold else F)[size],fill=c)
        text(40,24,'Reducing the Maxwell discrepancy',44,bold=True)
        text(40,83,'Same wedge and ports • Independent FDFD reference • Native 3D ray exports retained',24,MUTED)
        text(1170,34,f'{ch+1:02d} / 06   •   {t:04.1f} s',28,MUTED)
        text(40,117,title+'  •  '+name.replace('_',' / ')+'  •  2D line-source fields',22)
        for engine,x in [('sionna',40),('differt',820)]:
            color=COLORS[engine];r=self.groups[engine+'-reciprocal',name];entries=[a for a in r['entries'] if a['source']==source]
            baseline=z([e['prediction'] for e in entries]);full=z([e['refined'] for e in entries]);reference=z([e['reference'] for e in entries]);value=full if refined else baseline
            m=r['refined_metrics'] if refined else r;u,ref=value[j],reference[j]
            d.rounded_rectangle((x,157,x+740,811),18,fill=PANEL)
            text(x+24,174,'Sionna RT' if engine=='sionna' else 'DiffeRT',32,color,True)
            text(x+24,218,'+ full-wave 2D solve' if refined else 'reciprocal ray profile',20,MUTED)
            text(x+340,179,f'{100*m["total_complex_rms"]:.3f}%',38,color,True)
            text(x+525,193,'complex RMS error',19,MUTED)
            if ch==5:
                text(x+28,275,'Concrete / Hz • 265 channels',24,bold=True)
                before=100*r['total_complex_rms'];after=100*r['refined_metrics']['total_complex_rms']
                text(x+28,338,'Ray model',22);d.rounded_rectangle((x+180,338,x+180+before*88,372),7,fill='#72889a');text(x+205+before*88,338,f'{before:.2f}%',22)
                text(x+28,408,'Full-wave 2D',22);d.rectangle((x+180,408,x+180+max(3,after*88),442),fill=color);text(x+208,408,f'{after:.3f}%',22,color)
                text(x+28,505,'0.018–0.050% across eight groups',28,color,True)
                text(x+28,556,'Validated against a separate Maxwell method.',22)
                text(x+28,610,'A separate 2D field solver; native UTD is unchanged.',20,MUTED)
                text(x+28,650,'Extra obstacles and unsupported 3D scenes are rejected.',20,MUTED)
                text(x+28,690,'No fitted material or angle correction.',20,MUTED)
                text(x+28,747,'Both engine runtimes and Blender remain available.',20,MUTED)
                continue
            cx,cy=x+164,414;scale=29
            point=lambda q:(cx+float(q[0])*scale,cy-float(q[1])*scale)
            d.rectangle((cx,cy-132,cx+132,cy),fill='#33495b')
            d.line((cx-138,cy,cx+138,cy),fill=GRID);d.line((cx,cy-138,cx,cy+138),fill=GRID)
            c=self.cases[f'{name}_source{source}'];row=self.raw[engine][c['name']]
            for p in [p for p in row['paths'] if p['rx']==j]:d.line([point(q) for q in p['points']],fill=color if 8 in p['interactions'] else '#648095',width=3 if 8 in p['interactions'] else 2)
            for label,q in [('TX',c['tx']),('RX',c['receivers'][j])]:
                a,b=point(q);d.ellipse((a-6,b-6,a+6,b+6),fill=WHITE if label=='TX' else color);text(a+9,b-12,label,17)
            text(x+24,252,'Original ray geometry • λ = 1',20,MUTED)
            text(x+24,555,f'RX angle {entries[j]["angle_deg"]:.1f}° • 53 samples',17,MUTED)
            gx,gy,gw,gh=x+345,287,365,184
            def chart(vals,lo,hi,y0,height,c,width=3):
                pts=[(gx+k/52*gw,y0+height*(1-np.clip((v-lo)/(hi-lo),0,1))) for k,v in enumerate(vals)];d.line(pts,fill=c,width=width)
            text(gx,249,'Total field • dB re unit source',20,MUTED)
            for v in (-60,-40,-20):
                yy=gy+gh*(1-(v+70)/55);d.line((gx,yy,gx+gw,yy),fill=GRID);text(gx-32,yy-10,str(v),17,MUTED)
            if refined:chart(20*np.log10(abs(baseline)),-70,-15,gy,gh,'#72889a',2)
            chart(20*np.log10(abs(reference)),-70,-15,gy,gh,WHITE,4);chart(20*np.log10(abs(value)),-70,-15,gy,gh,color,2)
            xx=gx+j/52*gw;d.line((xx,gy,xx,gy+gh),fill=MUTED)
            for v,col in ((reference[j],WHITE),(value[j],color)):
                yy=gy+gh*(1-np.clip((20*np.log10(abs(v))+70)/55,0,1));d.ellipse((xx-4,yy-4,xx+4,yy+4),fill=col)
            text(gx,477,'5°',17,MUTED);text(gx+gw-38,477,'265°',17,MUTED)
            limit=1 if refined else 45;phase=np.rad2deg(np.angle(value/reference));py,ph=564,122
            text(gx,520,f'Phase error • ±{limit}°'+(' zoom' if refined else ''),20,MUTED)
            for v in (-limit,0,limit):
                yy=py+ph*(1-(v+limit)/(2*limit));d.line((gx,yy,gx+gw,yy),fill=GRID);text(gx-30,yy-10,str(v),17,MUTED)
            chart(phase,-limit,limit,py,ph,color);d.line((xx,py,xx,py+ph),fill=MUTED)
            text(gx,711,f'Δ phase  {np.rad2deg(np.angle(u/ref)):+.3f}°',24,color,True)
            text(gx,749,f'Δ magnitude  {20*np.log10(abs(u/ref)):+.3f} dB',22)
            pc=(x+156,680);rad=64;d.ellipse((pc[0]-rad,pc[1]-rad,pc[0]+rad,pc[1]+rad),outline=GRID,width=2)
            for v,col in ((ref,WHITE),(u,color)):
                a=np.angle(v);d.line((*pc,pc[0]+rad*np.cos(a),pc[1]-rad*np.sin(a)),fill=col,width=3)
            text(x+51,765,'Unit phasors: phase only',17,MUTED)
        d.line((40,845,1560,845),fill=GRID,width=3);d.line((40,845,40+1520*t/60,845),fill='#76ddb2',width=4)
        text(40,858,'White: FDFD • Color: labelled mode • Gray: ray baseline • Full-wave result is shared by both workflows',19,MUTED)
        return im

def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--previews',action='store_true');args=ap.parse_args();root=args.root.resolve()
    out=root/'outputs/differt-bridge/examples/maxwell_refinement';out.mkdir(parents=True,exist_ok=True);frames=root/'work/maxwell-refinement/frames';frames.mkdir(parents=True,exist_ok=True);renderer=Renderer(root)
    previews=[121,361,601,841,1081,1321]
    for frame in previews if args.previews else range(1,1441):
        im=renderer.render(frame);im.save(frames/f'frame_{frame:04d}.png',compress_level=1)
        if frame in previews:
            dest=out/'previews';dest.mkdir(exist_ok=True);im.save(dest/f'frame_{frame:04d}.png')
        if frame%240==1:print('FRAME',frame,flush=True)
    if not args.previews:
        files=sorted(frames.glob('frame_*.png'));assert len(files)==1440
        (root/'work/maxwell-refinement/frame_hashes.json').write_text(json.dumps({f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files},indent=2))
        meta=dict(status='frames_ready',frames=1440,fps=24,width=1600,height=900,duration_seconds=60,preview_frames=previews,frame_folder=frames.relative_to(root).as_posix(),analysis_sha256=hashlib.sha256((root/'work/maxwell-refinement/analysis.json').read_bytes()).hexdigest(),video_name='Sionna_vs_DiffeRT_2D_Refinement.mp4',timeline_name='Maxwell_Refinement_Animation.blend',chapters=[dict(start_seconds=c[0],title=c[1]) for c in CHAPTERS])
        (out/'animation_validation.json').write_text(json.dumps(meta,indent=2))

if __name__=='__main__':main()
