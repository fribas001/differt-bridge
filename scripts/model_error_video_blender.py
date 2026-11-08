"""Encode or independently decode the measured comparison using Blender 5.2."""
import sys,json,hashlib
from pathlib import Path
import bpy

root,mode,*extra=sys.argv[sys.argv.index('--')+1:];root=Path(root).resolve()
out=Path(extra[0]).resolve() if extra else root/'outputs/differt-bridge/examples/diffraction_model_errors'
data=json.loads((out/'animation_validation.json').read_text())
scene=bpy.context.scene;editor=scene.sequence_editor_create();movie=out/data.get('video_name','Sionna_vs_DiffeRT_Maxwell.mp4')
scene.render.resolution_x=1600;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene.render.fps=24;scene.frame_start=1;scene.frame_end=1440;scene.render.use_sequencer=True
scene.view_settings.view_transform='Standard';scene.render.threads_mode='FIXED';scene.render.threads=4
if mode=='encode':
    files=sorted((root/data['frame_folder']).glob('frame_*.png'));assert len(files)==1440
    strip=editor.strips.new_image('Measured fields versus Maxwell',str(files[0]),channel=1,frame_start=1)
    for f in files[1:]:strip.elements.append(f.name)
    strip.frame_final_duration=1440
    scene.render.image_settings.media_type='VIDEO';scene.render.image_settings.file_format='FFMPEG'
    scene.render.ffmpeg.format='MPEG4';scene.render.ffmpeg.codec='H264';scene.render.ffmpeg.constant_rate_factor='HIGH'
    scene.render.ffmpeg.ffmpeg_preset='GOOD';scene.render.ffmpeg.audio_codec='NONE';scene.render.filepath=str(movie)
    bpy.ops.render.render(animation=True)
    assert movie.stat().st_size>100000
    data.update(status='encoded',video_sha256=hashlib.sha256(movie.read_bytes()).hexdigest(),blender=bpy.app.version_string)
    (out/'animation_validation.json').write_text(json.dumps(data,indent=2))
elif mode=='verify':
    strip=editor.strips.new_movie('Sionna and DiffeRT versus Maxwell',str(movie),channel=1,frame_start=1)
    assert strip.elements[0].orig_width==1600 and strip.elements[0].orig_height==900
    assert strip.frame_duration==1440 and abs(strip.fps-24)<1e-6
    assert hashlib.sha256(movie.read_bytes()).hexdigest()==data['video_sha256']
    scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
    decoded=out/'decoded';decoded.mkdir(exist_ok=True)
    for frame in data['preview_frames']:
        scene.frame_set(frame);scene.render.filepath=str(decoded/f'frame_{frame:04d}.png');bpy.ops.render.render(write_still=True)
    for c in data['chapters']:scene.timeline_markers.new(c['title'],frame=1+int(c['start_seconds']*24))
    scene.frame_set(1);bpy.context.preferences.filepaths.save_version=0
    target=out/data.get('timeline_name','Maxwell_Comparison_Animation.blend');bpy.ops.wm.save_as_mainfile(filepath=str(target))
    bpy.ops.file.make_paths_relative();bpy.ops.wm.save_as_mainfile(filepath=str(target));bpy.ops.wm.open_mainfile(filepath=str(target))
    strip=next(s for s in bpy.context.scene.sequence_editor.strips if s.type=='MOVIE')
    assert strip.filepath.startswith('//') and Path(bpy.path.abspath(strip.filepath)).exists()
    (out/'video_validation.json').write_text(json.dumps(dict(status='passed',width=1600,height=900,frames=1440,fps=24,duration_seconds=60,verified_sample_frames=data['preview_frames'],blender=bpy.app.version_string,relative_movie_path=strip.filepath,saved_and_reopened=True),indent=2))
else:raise ValueError(mode)
print('MODEL_ERROR_VIDEO_'+mode.upper()+'_PASS',flush=True)
