import React, {useEffect, useState} from 'react';
import {
  AbsoluteFill,
  OffthreadVideo,
  Sequence,
  continueRender,
  delayRender,
  getStaticFiles,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {SERIES_TITLE} from './data/reels';
import type {Reel} from './data/types.ts';
import {SceneView, SourceTag} from './components/Scenes';
import {C, FONT, VIDEO_H} from './theme';

const useFonts = () => {
  const [handle] = useState(() => delayRender('Loading Cairo font'));
  useEffect(() => {
    Promise.all(['400', '700', '800', '900'].map((w) => document.fonts.load(`${w} 40px Cairo`, 'ع')))
      .then(() => continueRender(handle))
      .catch(() => continueRender(handle));
  }, [handle]);
};

const SpeakerArea: React.FC<{reel: Reel}> = ({reel}) => {
  const file = `videos/${reel.id}.mp4`;
  const hasVideo = getStaticFiles().some((f) => f.name === file);
  return (
    <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: VIDEO_H, overflow: 'hidden'}}>
      {hasVideo ? (
        <OffthreadVideo src={staticFile(file)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      ) : (
        <AbsoluteFill
          style={{
            background: `linear-gradient(160deg, #1D4A52, ${C.bg})`,
            alignItems: 'center',
            justifyContent: 'center',
            gap: 24,
            fontFamily: FONT,
            color: C.muted,
          }}
        >
          <svg width="260" height="260" viewBox="0 0 100 100">
            <circle cx="50" cy="36" r="18" fill="#2E6069" />
            <path d="M14 96c0-22 16-36 36-36s36 14 36 36z" fill="#2E6069" />
          </svg>
          <div style={{fontSize: 44, fontWeight: 700}}>مكان الفيديو بتاعك</div>
          <div style={{fontSize: 30, direction: 'ltr'}}>{`public/${file}`}</div>
        </AbsoluteFill>
      )}
      <div
        style={{
          position: 'absolute',
          top: 60,
          right: 50,
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          padding: '12px 28px',
          borderRadius: 999,
          background: '#0B1F24cc',
          border: `2px solid ${C.green}66`,
          fontFamily: FONT,
          fontSize: 32,
          fontWeight: 700,
          color: C.text,
          direction: 'rtl',
        }}
      >
        <span style={{width: 14, height: 14, borderRadius: 99, background: C.green}} />
        {SERIES_TITLE} • الحلقة {reel.number}
      </div>
    </div>
  );
};

const PanelBackground: React.FC = () => {
  const frame = useCurrentFrame();
  const a = frame / 90;
  return (
    <AbsoluteFill style={{background: `linear-gradient(180deg, ${C.panel}, ${C.bg})`, overflow: 'hidden'}}>
      <div
        style={{
          position: 'absolute',
          width: 700,
          height: 700,
          borderRadius: 999,
          background: `${C.green}22`,
          filter: 'blur(120px)',
          left: 100 + Math.sin(a) * 180,
          top: 80 + Math.cos(a * 0.8) * 120,
        }}
      />
      <div
        style={{
          position: 'absolute',
          width: 600,
          height: 600,
          borderRadius: 999,
          background: `${C.gold}14`,
          filter: 'blur(120px)',
          right: 60 + Math.cos(a * 0.7) * 160,
          bottom: 40 + Math.sin(a * 0.9) * 120,
        }}
      />
    </AbsoluteFill>
  );
};

export const ReelComposition: React.FC<{reel: Reel}> = ({reel}) => {
  useFonts();
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const progress = interpolate(frame, [0, durationInFrames - 1], [0, 100]);
  return (
    <AbsoluteFill style={{background: C.bg}}>
      <SpeakerArea reel={reel} />
      <div
        style={{
          position: 'absolute',
          top: VIDEO_H - 40,
          left: 0,
          right: 0,
          bottom: 0,
          borderRadius: '44px 44px 0 0',
          overflow: 'hidden',
          boxShadow: '0 -20px 60px #0008',
        }}
      >
        <PanelBackground />
        {reel.scenes.map((s, i) => (
          <Sequence key={i} from={Math.round(s.at * fps)} durationInFrames={Math.round(s.dur * fps)} layout="none">
            <SceneView scene={s} />
            {s.source && <SourceTag source={s.source} />}
          </Sequence>
        ))}
        <div style={{position: 'absolute', bottom: 0, right: 0, height: 12, width: `${progress}%`, background: C.green}} />
      </div>
    </AbsoluteFill>
  );
};
