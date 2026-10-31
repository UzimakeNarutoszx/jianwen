import React from 'react';
import {Audio, Video} from '@remotion/media';
import {CanvasImage, Composition, Folder, Interactive, Sequence, Still, Track, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import episode from './current-episode';

const ink = '#14212b', blue = '#1f5f7a', paper = '#f5f7f4';
const font = '"PingFang SC", "Microsoft YaHei", sans-serif';
type ChapterName = '片头导读' | '本周重点文章' | '本周见闻更新' | '大事总结' | '片尾来源';
type ChapterProps = {chapter: ChapterName};
const chapterStart = (chapter: string) => episode.chapters.find(item => item.title === chapter)!.seconds;
const chapterDuration = (chapter: string) => {
  const index = episode.chapters.findIndex(item => item.title === chapter);
  return (episode.chapters[index + 1]?.seconds ?? episode.durationSeconds) - episode.chapters[index].seconds;
};

const Identity: React.FC<{frames: number}> = ({frames}) => {
  const frame = useCurrentFrame();
  return <div style={{position: 'absolute', right: 0, top: 180, width: 920, height: 520}}>
    {frame < frames ? <Sequence durationInFrames={frames} layout="none"><Video src={staticFile('identity/identity.mp4')} muted objectFit="cover" style={{width:'100%', height:'100%'}} /></Sequence>
      : <CanvasImage src={staticFile('identity/hold.jpg')} style={{width: '100%', height: '100%'}} />}
  </div>;
};

const ChapterInner: React.FC<ChapterProps> = ({chapter}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const chapterFrames = Math.round(chapterDuration(chapter) * fps);
  // Short chapters (e.g. a ~1 minute episode) must not overflow the 72-frame identity intro.
  const identityFrames = Math.max(1, Math.min(72, chapterFrames));
  const globalSeconds = frame / fps + chapterStart(chapter);
  const slides = episode.slides.filter(item => item.chapter === chapter);
  const slide = slides.find(item => globalSeconds >= item.start && globalSeconds < item.end) || slides[0];
  const cue = episode.cues.find(item => globalSeconds >= item.start && globalSeconds < item.end);
  const elapsed = (globalSeconds - slide.start) * fps;
  const title = chapter === '片头导读' ? '把一周，\n串起来。' : slide.title;
  const isBookend = chapter === '片头导读' || chapter === '片尾来源';
  return <div style={{position:'absolute', inset:0, background:paper, fontFamily:font, color:ink}}>
    <div style={{position:'absolute', left:104, right:104, top:64, display:'flex', justifyContent:'space-between', fontSize:26, color:blue, borderBottom:'1px solid #bfcdd0', paddingBottom:22}}>
      <span style={{fontWeight:600}}>见闻 / 每周视频</span><span>第 {episode.number} 期 · {episode.weekStart}—{episode.weekEnd}</span>
    </div>
    {isBookend && <Identity frames={identityFrames} />}
    {!isBookend && frame < identityFrames && <Sequence durationInFrames={identityFrames}><Video src={staticFile('identity/identity.mp4')} muted style={{position:'absolute',right:20,top:120,width:360,height:203,opacity:.4}} /></Sequence>}
    <div style={{position:'absolute', left:104, top:168, fontSize:28, color:blue}}>{chapter}</div>
    <div style={{position:'absolute', left:104, right:104, top:232, display:'grid', gridTemplateColumns:isBookend ? '1fr 1fr' : '1.05fr 1fr', gap:96, alignItems:'start'}}>
      <h1 style={{fontFamily:'"Songti SC", "STSong", serif', fontSize:isBookend ? 100 : 76, lineHeight:1.28, fontWeight:600, letterSpacing:'-.02em', whiteSpace:'pre-line', margin:0,
        opacity:interpolate(elapsed,[0,.5*fps],[.3,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'}),
        translate:`0 ${interpolate(elapsed,[0,.6*fps],[22,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}px`}}>{title}</h1>
      {!isBookend && <div style={{paddingTop:12}}>{slide.lines.map((line,index) => <div key={line} style={{padding:'24px 0', borderTop:'1px solid #b9cace', fontSize:index === 0 && line.includes('万亿') ? 70 : 36, lineHeight:1.5, color:index === 0 ? blue : ink,
        opacity:interpolate(elapsed,[index*.3*fps,(index*.3+.7)*fps],[.22,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'})}}>{line}</div>)}</div>}
    </div>
    {isBookend && <div style={{position:'absolute', left:104, top:590, maxWidth:760, fontSize:30, lineHeight:1.9, color:blue}}>{slide.lines.map(line => <div key={line}>{line}</div>)}</div>}
    {chapter === '片尾来源' && (episode as typeof episode & {soundtrack?: {credit: string}}).soundtrack && <div style={{position:'absolute',left:104,bottom:215,fontSize:23,color:blue}}>{(episode as typeof episode & {soundtrack?: {credit: string}}).soundtrack?.credit}</div>}
    <div style={{position:'absolute', left:104, right:104, bottom:170, display:'flex', alignItems:'center', gap:16, color:blue, fontSize:23}}><span style={{width:28,height:2,background:'#b08a35'}} />{slide.source}</div>
    <div style={{position:'absolute', left:104, right:104, bottom:62, minHeight:66, borderTop:'1px solid #bfcdd0', paddingTop:22, display:'flex', justifyContent:'center', fontSize:34, lineHeight:1.6}}>{cue?.text || '\u00a0'}</div>
    <div style={{position:'absolute',left:0,bottom:0,height:5,background:blue,width:`${globalSeconds / episode.durationSeconds * 100}%`}} />
  </div>;
};

export const Chapter = Interactive.create({Component: ChapterInner, layout:'absolute-fill'});

export const WeeklyVideo = () => {
  const {fps} = useVideoConfig();
  const soundtrack = (episode as typeof episode & {soundtrack?: {file: string}}).soundtrack;
  return <>
    <Track name="节目章节">
      <Chapter name="片头导读" chapter="片头导读" durationInFrames={Math.round(chapterDuration('片头导读') * fps)} />
      <Chapter name="本周重点文章" chapter="本周重点文章" from={Math.round(chapterStart('本周重点文章') * fps)} durationInFrames={Math.round(chapterDuration('本周重点文章') * fps)} />
      <Chapter name="本周见闻更新" chapter="本周见闻更新" from={Math.round(chapterStart('本周见闻更新') * fps)} durationInFrames={Math.round(chapterDuration('本周见闻更新') * fps)} />
      <Chapter name="大事总结" chapter="大事总结" from={Math.round(chapterStart('大事总结') * fps)} durationInFrames={Math.round(chapterDuration('大事总结') * fps)} />
      <Chapter name="片尾来源" chapter="片尾来源" from={Math.round(chapterStart('片尾来源') * fps)} durationInFrames={Math.round(chapterDuration('片尾来源') * fps)} />
    </Track>
    <Audio name={soundtrack ? '旁白与原创配乐《雨》' : '中文旁白'} src={soundtrack ? staticFile(`episodes/${episode.id}/${soundtrack.file}`) : `${staticFile(`episodes/${episode.id}/narration.m4a`)}?v=${encodeURIComponent(episode.voice.engine)}-${episode.durationInFrames}`} />
  </>;
};

export const Cover = () => <div style={{position:'absolute', inset:0, background:paper, color:ink, fontFamily:font}}>
  <CanvasImage src={staticFile('identity/hold.jpg')} style={{position:'absolute',right:0,top:170,width:1100,height:620}} />
  <div style={{position:'absolute',left:104,right:104,top:70,fontSize:28,color:blue,display:'flex',justifyContent:'space-between',borderBottom:'1px solid #bfcdd0',paddingBottom:22}}><span>见闻 / 每周视频</span><span>第 {episode.number} 期</span></div>
  <h1 style={{position:'absolute',left:104,top:238,margin:0,fontFamily:'"Songti SC", serif',fontSize:110,lineHeight:1.3}}>把一周，<br/>串起来。</h1>
  <div style={{position:'absolute',left:104,bottom:160,fontSize:32,color:blue}}>重点文章 · 见闻更新 · 大事总结</div>
  <div style={{position:'absolute',left:104,bottom:90,fontSize:27,color:blue}}>{episode.weekStart}—{episode.weekEnd} · 截至 {episode.cutoff.slice(0,10)}</div>
</div>;

export const Registrations = () => <>
  <Composition id="WeeklyVideo" component={WeeklyVideo} width={1920} height={1080} fps={30} durationInFrames={episode.durationInFrames} />
  <Still id="WeeklyCover" component={Cover} width={1920} height={1080} />
  <Folder name="Chapters">
    <Composition id="Chapter" component={Chapter} width={1920} height={1080} fps={30} durationInFrames={Math.round(chapterDuration('本周重点文章') * 30)} defaultProps={{chapter:'本周重点文章'}} />
  </Folder>
</>;
