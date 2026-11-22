import React from 'react';
import {Audio} from '@remotion/media';
import {CanvasImage, Composition, Folder, Sequence, Still, Track, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import episodeJson from './current-episode';

/* ---------------------------------------------------------------------------
   见闻每周视频 · v2 版式
   纸页 + 索引 + 印章。每一屏是一张翻过来的纸：左边落章名与标题，右边放这一条的
   实际证据（批注 / 微型界面 / 数字），底部是日刻度、出处与逐字字幕。
   --------------------------------------------------------------------------- */

const paper = '#efece1', sheet = '#fbfaf3', ink = '#16222b', blue = '#1f5f7a';
const gold = '#b08a35', seal = '#a2402d', rule = '#c7d0cc', muted = '#71807f';
const serif = '"Songti SC", "STSong", serif';
const sans = '"PingFang SC", "Microsoft YaHei", sans-serif';
const M = 72;
const days = ['一', '二', '三', '四', '五', '六', '日'];
const chapters = ['片头导读', '本周重点文章', '本周见闻更新', '大事总结', '片尾来源'];

type Kind = 'cover' | 'text' | 'ui' | 'figures';
type Slide = {
  chapter: string; title: string; lines?: string[]; narration: string; source: string;
  kind?: Kind; day?: string; start: number; end: number;
  ui?: {brand: string; url: string; cardTitle: string; cardDesc: string; cardAction: string; footer: string};
  figures?: {value: string; label: string}[];
};
type Episode = {
  id: string; number: number; weekStart: string; weekEnd: string; cutoff: string;
  durationSeconds: number; durationInFrames: number; slides: Slide[];
  chapters: {title: string; seconds: number}[];
  cues: {start: number; end: number; text: string}[];
  soundtrack?: {file: string; credit: string};
  voice: {engine: string};
};
const episode = episodeJson as unknown as Episode;

const chapterStart = (title: string) => episode.chapters.find(item => item.title === title)!.seconds;
const chapterDuration = (title: string) => {
  const index = episode.chapters.findIndex(item => item.title === title);
  return (episode.chapters[index + 1]?.seconds ?? episode.durationSeconds) - episode.chapters[index].seconds;
};

/** 纸页进场：一上手就停，不回弹。 */
const sheetIn = (frame: number) =>
  spring({frame, fps: 30, config: {stiffness: 1200, damping: 80}, durationInFrames: 16});

/** 行/块进场：纸页落下后 0.2–0.4s 跟上。 */
const rise = (frame: number, delay: number, distance = 16) => {
  const t = spring({frame: frame - delay, fps: 30, config: {stiffness: 1200, damping: 80}, durationInFrames: 18});
  return {opacity: t, transform: `translateY(${(1 - t) * distance}px)`};
};

/** 逐字渐显：blur 6px → 0，单字 120ms，字间错开 30ms。 */
const Subtitle: React.FC<{text: string}> = ({text}) => {
  const frame = useCurrentFrame();
  return <div style={{fontSize: 33, lineHeight: 1.55, color: ink, display: 'flex', flexWrap: 'wrap', justifyContent: 'center'}}>
    {[...text].map((char, index) => {
      const local = frame - index * 0.9;
      const opacity = interpolate(local, [0, 3.6], [0.12, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
      const blur = interpolate(local, [0, 3.6], [6, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
      return <span key={`${char}-${index}`} style={{opacity, filter: `blur(${blur}px)`}}>{char}</span>;
    })}
  </div>;
};

const Seal: React.FC<{number: number}> = ({number}) => (
  <div style={{
    width: 74, height: 74, borderRadius: 6, background: seal, color: '#fbf3e4',
    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
    fontFamily: serif, transform: 'rotate(-3.5deg)', boxShadow: '0 6px 18px rgba(162,64,45,.18)', gap: 1,
  }}>
    <span style={{fontSize: 12, letterSpacing: 2, opacity: .82}}>第</span>
    <span style={{fontSize: 28, lineHeight: 1}}>{number}</span>
    <span style={{fontSize: 12, letterSpacing: 2, opacity: .82}}>期</span>
  </div>
);

const IndexRail: React.FC<{active: string}> = ({active}) => (
  <div style={{display: 'flex', alignItems: 'center', gap: 26, fontSize: 19}}>
    {chapters.map(name => {
      const on = name === active;
      return <span key={name} style={{color: on ? ink : muted, fontWeight: on ? 500 : 400, position: 'relative', whiteSpace: 'nowrap'}}>
        {name}
        <span style={{position: 'absolute', left: 0, right: 0, bottom: -10, height: 2, background: on ? gold : 'transparent'}} />
      </span>;
    })}
  </div>
);

/** 底部日刻度：11 月 16—22，这一条落在哪一天。 */
const DayStrip: React.FC<{day?: string}> = ({day}) => {
  const frame = useCurrentFrame();
  const activeIndex = day ? days.indexOf(day) : -1;
  return <div style={{display: 'flex', alignItems: 'flex-end', gap: 18, fontVariantNumeric: 'tabular-nums'}}>
    <span style={{fontSize: 18, color: muted, letterSpacing: 1, paddingBottom: 2}}>11 月</span>
    {days.map((label, index) => {
      const on = index === activeIndex;
      const done = activeIndex < 0 || index <= activeIndex;
      const t = spring({frame: frame - 6 - index * 2, fps: 30, config: {stiffness: 1200, damping: 80}, durationInFrames: 14});
      return <div key={label} style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5, opacity: t}}>
        <span style={{fontSize: on ? 26 : 22, color: on ? seal : done ? ink : rule, fontWeight: on ? 600 : 400}}>{16 + index}</span>
        <span style={{width: on ? 7 : 5, height: on ? 7 : 5, borderRadius: 4, background: on ? seal : done ? rule : 'transparent'}} />
        <span style={{fontSize: 14, color: on ? seal : muted}}>{label}</span>
      </div>;
    })}
  </div>;
};

/** 纸页：两层底页露一点边，翻页时整叠往下推、略歪。 */
const SheetShell: React.FC<{children: React.ReactNode; frame: number}> = ({children, frame}) => {
  const t = sheetIn(frame);
  return <div style={{position: 'absolute', inset: 0, background: paper, fontFamily: sans, color: ink, overflow: 'hidden'}}>
    <div style={{position: 'absolute', inset: 10, background: '#e6e1d2', transform: `rotate(${-0.5 - (1 - t) * 0.5}deg)`}} />
    <div style={{position: 'absolute', inset: 5, background: '#f2efe4', transform: `rotate(${-0.22 - (1 - t) * 0.3}deg)`}} />
    <div style={{
      position: 'absolute', inset: 0, background: sheet, boxShadow: '0 34px 80px rgba(22,34,43,.12)',
      transform: `translateY(${(1 - t) * 54}px) rotate(${(1 - t) * -1.1}deg)`, opacity: t,
    }}>{children}</div>
  </div>;
};

const Head: React.FC<{active: string; frame: number}> = ({active, frame}) => {
  const ruleScale = interpolate(frame, [2, 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <>
    <div style={{position: 'absolute', left: M, right: M, top: 58, display: 'flex', alignItems: 'baseline', justifyContent: 'space-between'}}>
      <div style={{display: 'flex', alignItems: 'baseline', gap: 16}}>
        <span style={{fontSize: 23, letterSpacing: '.14em', color: blue, fontWeight: 600}}>见闻</span>
        <span style={{fontSize: 19, color: muted, letterSpacing: '.06em'}}>每周视频</span>
        <span style={{fontSize: 19, color: ink, fontVariantNumeric: 'tabular-nums'}}>第 {episode.number} 期</span>
      </div>
      <IndexRail active={active} />
    </div>
    <div style={{position: 'absolute', left: M, right: M, top: 116, height: 1, background: rule, transformOrigin: 'left center', transform: `scaleX(${ruleScale})`}} />
  </>;
};

const Foot: React.FC<{slide: Slide; progress: number}> = ({slide, progress}) => (
  <>
    <div style={{position: 'absolute', left: M, right: M, top: 884, height: 1, background: rule}} />
    <div style={{position: 'absolute', left: M, top: 902}}><DayStrip day={slide.day} /></div>
    <div style={{position: 'absolute', right: 168, top: 912, display: 'flex', alignItems: 'center', gap: 12, fontSize: 20, color: muted}}>
      <span style={{width: 22, height: 2, background: gold}} />
      {slide.source}
    </div>
    <div style={{position: 'absolute', left: 0, bottom: 0, height: 4, width: `${progress * 100}%`, background: blue}} />
  </>
);

/** 微型界面：把「个人网站」这张卡片真的画出来，光标走过去点一下。 */
const MiniSite: React.FC<{ui: NonNullable<Slide['ui']>; frame: number}> = ({ui, frame}) => {
  const enter = spring({frame: frame - 14, fps: 30, config: {stiffness: 1200, damping: 80}, durationInFrames: 18});
  const travel = interpolate(frame, [26, 56], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const eased = travel * travel * (3 - 2 * travel);
  const pressed = frame >= 56;
  const ripple = interpolate(frame, [56, 78], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const lift = pressed ? interpolate(frame, [56, 66], [0, -3], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 0;
  return <div style={{
    width: 720, height: 430, background: '#ffffff', borderRadius: 14, overflow: 'hidden', position: 'relative',
    boxShadow: '0 24px 60px rgba(22,34,43,.14), inset 0 0 0 1px rgba(22,34,43,.05)',
    transform: `translateY(${(1 - enter) * 26}px)`, opacity: enter,
  }}>
    <div style={{height: 52, display: 'flex', alignItems: 'center', gap: 10, padding: '0 18px', background: '#f7f6f0', boxShadow: 'inset 0 -1px 0 rgba(22,34,43,.05)'}}>
      <span style={{width: 9, height: 9, borderRadius: 9, background: '#ddd9cb'}} />
      <span style={{width: 9, height: 9, borderRadius: 9, background: '#ddd9cb'}} />
      <span style={{width: 9, height: 9, borderRadius: 9, background: '#ddd9cb'}} />
      <div style={{marginLeft: 12, flex: 1, height: 28, borderRadius: 8, background: '#efeee6', display: 'flex', alignItems: 'center', padding: '0 12px', fontSize: 15, color: muted}}>{ui.url}</div>
    </div>
    <div style={{padding: '26px 30px'}}>
      <div style={{display: 'flex', alignItems: 'baseline', gap: 10}}>
        <span style={{fontFamily: serif, fontSize: 26, fontWeight: 600, color: ink}}>{ui.brand}</span>
        <span style={{fontSize: 14, color: muted}}>保持好奇，也保持思考。</span>
      </div>
      <div style={{
        marginTop: 20, padding: '22px 24px', borderRadius: 12, background: '#f8f7f1',
        boxShadow: 'inset 0 0 0 1px rgba(31,95,122,.12)', transform: `translateY(${lift}px)`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div>
          <div style={{fontSize: 13, color: blue, letterSpacing: '.08em'}}>新入口</div>
          <div style={{fontFamily: serif, fontSize: 30, fontWeight: 600, marginTop: 6}}>{ui.cardTitle}</div>
          <div style={{fontSize: 15, color: muted, marginTop: 6}}>{ui.cardDesc}</div>
        </div>
        <div style={{position: 'relative'}}>
          <div style={{padding: '11px 22px', borderRadius: 10, fontSize: 16, color: '#fbfaf3', background: pressed && frame >= 58 ? blue : ink, letterSpacing: '.04em'}}>{ui.cardAction}</div>
          {ripple > 0 && ripple < 1 && <span style={{position: 'absolute', inset: -6, borderRadius: 14, border: `2px solid ${blue}`, opacity: 1 - ripple, transform: `scale(${1 + ripple * 0.35})`}} />}
        </div>
      </div>
      <div style={{marginTop: 18, display: 'flex', gap: 18, fontSize: 14, color: muted}}>
        {ui.footer.split(' · ').map(item => <span key={item}>{item}</span>)}
      </div>
    </div>
    <div style={{position: 'absolute', left: 96 + eased * 540, top: 300 - eased * 84, opacity: interpolate(frame, [22, 28], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>
      <svg width="24" height="28" viewBox="0 0 24 28"><path d="M2 2 L2 21 L7.4 16.4 L11 24.4 L14.6 22.9 L11 15 L17.6 14.6 Z" fill={ink} stroke="#fbfaf3" strokeWidth="1.6" strokeLinejoin="round" /></svg>
    </div>
  </div>;
};

const Figures: React.FC<{items: NonNullable<Slide['figures']>; frame: number}> = ({items, frame}) => (
  <div style={{display: 'flex', alignItems: 'flex-start'}}>
    {items.map((item, index) => {
      const style = rise(frame, 16 + index * 7, 22);
      const size = [...item.value].length > 4 ? 74 : 96;
      return <div key={item.value} style={{...style, padding: '8px 34px 0', flex: index === 0 ? 1.3 : 1, boxShadow: index === 0 ? 'none' : `inset 1px 0 0 ${rule}`}}>
        <div style={{fontFamily: serif, fontSize: size, lineHeight: 1, fontWeight: 600, fontVariantNumeric: 'tabular-nums', letterSpacing: '-.02em', whiteSpace: 'nowrap'}}>{item.value}</div>
        <div style={{marginTop: 14, fontSize: 18, color: muted, letterSpacing: '.02em', whiteSpace: 'nowrap'}}>{item.label}</div>
      </div>;
    })}
  </div>
);

const Notes: React.FC<{lines: string[]; frame: number}> = ({lines, frame}) => (
  <div>
    {lines.map((line, index) => {
      const style = rise(frame, 14 + index * 6, 14);
      return <div key={line} style={{...style, display: 'flex', alignItems: 'baseline', gap: 16, padding: '20px 0', boxShadow: `inset 0 1px 0 ${rule}`}}>
        <span style={{width: 6, height: 6, borderRadius: 3, background: index === 0 ? blue : rule, flex: 'none', transform: 'translateY(-4px)'}} />
        <span style={{fontSize: index === 0 ? 27 : 25, lineHeight: 1.5, color: index === 0 ? blue : ink}}>{line}</span>
      </div>;
    })}
  </div>
);

const SlideBody: React.FC<{slide: Slide; frame: number}> = ({slide, frame}) => {
  const kind: Kind = slide.kind ?? 'text';
  const isCover = kind === 'cover';
  const titleStyle: React.CSSProperties = {margin: 0, fontFamily: serif, fontSize: isCover ? 96 : 74, lineHeight: 1.26, fontWeight: 600, letterSpacing: '-.015em', whiteSpace: 'pre-line'};
  return <>
    <div style={{position: 'absolute', left: M, top: 168, fontSize: 20, color: blue, letterSpacing: '.16em'}}>{slide.chapter}</div>
    <div style={{position: 'absolute', left: M, top: 210, width: isCover ? 760 : 860, ...rise(frame, 6, 20)}}>
      <h1 style={titleStyle}>{slide.title}</h1>
      {isCover && <div style={{marginTop: 34, display: 'flex', flexDirection: 'column', gap: 12, fontSize: 25, color: blue}}>
        {(slide.lines ?? []).map(line => <div key={line}>{line}</div>)}
      </div>}
      {!isCover && (kind === 'text' || kind === 'ui') && <div style={{marginTop: 40, width: kind === 'ui' ? 640 : 720}}><Notes lines={slide.lines ?? []} frame={frame} /></div>}
    </div>
    {!isCover && kind === 'text' && <div style={{position: 'absolute', right: M, top: 196, ...rise(frame, 10, 18)}}>
      <CanvasImage src={staticFile('identity/hold.jpg')} style={{width: 620, height: 430, objectFit: 'cover'}} />
      <div style={{marginTop: 14, fontSize: 15, color: muted, letterSpacing: '.04em'}}>Blender 建模渲染 · 见闻片头</div>
    </div>}
    {kind === 'ui' && <div style={{position: 'absolute', right: M, top: 196}}><MiniSite ui={slide.ui!} frame={frame} /></div>}
    {kind === 'figures' && <div style={{position: 'absolute', left: M, top: 520, width: 980}}><Figures items={slide.figures ?? []} frame={frame} /></div>}
    {isCover && <div style={{position: 'absolute', right: 40, top: 150, width: 900, height: 512, opacity: interpolate(frame, [4, 22], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>
      <CanvasImage src={staticFile('identity/hold.jpg')} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
    </div>}
  </>;
};

const ChapterSlides: React.FC<{chapter: string; from: number}> = ({chapter, from}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const global = from + frame / fps;
  const slides = episode.slides.filter(item => item.chapter === chapter);
  const slide = slides.find(item => global >= item.start && global < item.end) || slides[slides.length - 1];
  const localFrame = Math.round((global - slide.start) * fps);
  const cue = episode.cues.find(item => global >= item.start && global < item.end);
  return <SheetShell frame={localFrame}>
    <Head active={chapter} frame={localFrame} />
    <SlideBody slide={slide} frame={localFrame} />
    <Foot slide={slide} progress={global / episode.durationSeconds} />
    <div style={{position: 'absolute', right: M - 6, bottom: 200}}><Seal number={episode.number} /></div>
    {chapter === '片尾来源' && episode.soundtrack && <div style={{position: 'absolute', left: M, top: 848, fontSize: 15, color: muted, letterSpacing: '.04em'}}>{episode.soundtrack.credit}</div>}
    <div style={{position: 'absolute', left: 96, right: 96, bottom: 44, minHeight: 62}}>{cue ? <Subtitle text={cue.text} /> : null}</div>
  </SheetShell>;
};

export const WeeklyVideoV2: React.FC = () => {
  const {fps} = useVideoConfig();
  const soundtrack = episode.soundtrack;
  return <>
    <Track name="节目章节">
      {episode.chapters.map(item => (
        <Sequence key={item.title} from={Math.round(item.seconds * fps)} durationInFrames={Math.round(chapterDuration(item.title) * fps)} layout="none">
          <ChapterSlides chapter={item.title} from={item.seconds} />
        </Sequence>
      ))}
    </Track>
    <Audio name={soundtrack ? '旁白与原创配乐《雨》' : '中文旁白'} src={soundtrack ? staticFile(`episodes/${episode.id}/${soundtrack.file}`) : `${staticFile(`episodes/${episode.id}/narration.m4a`)}?v=${encodeURIComponent(episode.voice.engine)}-${episode.durationInFrames}`} />
  </>;
};

export const CoverV2: React.FC = () => (
  <div style={{position: 'absolute', inset: 0, background: paper, fontFamily: sans, color: ink, overflow: 'hidden'}}>
    <div style={{position: 'absolute', inset: 10, background: '#e6e1d2', transform: 'rotate(-0.5deg)'}} />
    <div style={{position: 'absolute', inset: 5, background: '#f2efe4', transform: 'rotate(-0.22deg)'}} />
    <div style={{position: 'absolute', inset: 0, background: sheet, boxShadow: '0 34px 80px rgba(22,34,43,.12)'}}>
      <div style={{position: 'absolute', left: M, right: M, top: 58, display: 'flex', alignItems: 'baseline', justifyContent: 'space-between'}}>
        <div style={{display: 'flex', alignItems: 'baseline', gap: 16}}>
          <span style={{fontSize: 23, letterSpacing: '.14em', color: blue, fontWeight: 600}}>见闻</span>
          <span style={{fontSize: 19, color: muted, letterSpacing: '.06em'}}>每周视频</span>
        </div>
        <span style={{fontSize: 19, color: ink}}>第 {episode.number} 期</span>
      </div>
      <div style={{position: 'absolute', left: M, right: M, top: 116, height: 1, background: rule}} />
      <h1 style={{position: 'absolute', left: M, top: 250, margin: 0, fontFamily: serif, fontSize: 104, lineHeight: 1.24, fontWeight: 600}}>把一周，<br />串起来。</h1>
      <div style={{position: 'absolute', left: M, top: 660, fontSize: 24, color: blue, display: 'flex', flexDirection: 'column', gap: 10}}>
        <span>重点文章 · 见闻更新 · 大事总结</span>
        <span style={{fontVariantNumeric: 'tabular-nums'}}>{episode.weekStart.replace(/-/g, '.')} — {episode.weekEnd.slice(5).replace('-', '.')}</span>
      </div>
      <CanvasImage src={staticFile('identity/hold.jpg')} style={{position: 'absolute', right: 20, top: 170, width: 940, height: 528}} />
      <div style={{position: 'absolute', right: M - 6, bottom: 92}}><Seal number={episode.number} /></div>
    </div>
  </div>
);

const ChapterDefault: React.FC<{chapter: string; from: number}> = ({chapter, from}) => <ChapterSlides chapter={chapter} from={from} />;

export const RegistrationsV2: React.FC = () => <>
  <Composition id="WeeklyVideo" component={WeeklyVideoV2} width={1920} height={1080} fps={30} durationInFrames={episode.durationInFrames} />
  <Still id="WeeklyCover" component={CoverV2} width={1920} height={1080} />
  <Folder name="Chapters">
    <Composition id="Chapter" component={ChapterDefault} width={1920} height={1080} fps={30} durationInFrames={Math.round(chapterDuration('本周重点文章') * 30)} defaultProps={{chapter: '本周重点文章', from: chapterStart('本周重点文章')}} />
  </Folder>
</>;
