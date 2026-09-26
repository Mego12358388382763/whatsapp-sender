import React from 'react';
import {Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Scene} from '../data/types.ts';
import {C, FONT} from '../theme';

const useAnim = () => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 200}});
  const exit = interpolate(frame, [durationInFrames - 10, durationInFrames], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return {frame, fps, durationInFrames, enter, exit};
};

const pop = (frame: number, fps: number, delay: number) =>
  spring({frame: frame - delay, fps, config: {damping: 14, stiffness: 120}});

const strip = (w: string) => w.replace(/[…؟?!:،,."]/g, '');

const Words: React.FC<{
  text: string;
  highlight?: string;
  size: number;
  weight?: number;
  stagger?: number;
}> = ({text, highlight, size, weight = 800, stagger = 3}) => {
  const {frame, fps} = useAnim();
  const hl = new Set((highlight ?? '').split(/\s+/).map(strip).filter(Boolean));
  const words = text.split(/\s+/);
  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        columnGap: size * 0.28,
        rowGap: size * 0.1,
        direction: 'rtl',
      }}
    >
      {words.map((w, i) => {
        const p = pop(frame, fps, i * stagger);
        const isHl = hl.has(strip(w));
        return (
          <span
            key={i}
            style={{
              fontSize: size,
              fontWeight: weight,
              lineHeight: 1.35,
              color: isHl ? C.gold : C.text,
              opacity: Math.min(1, p * 1.5),
              transform: `translateY(${(1 - p) * 40}px)`,
              display: 'inline-block',
              position: 'relative',
            }}
          >
            {w}
            {isHl && (
              <span
                style={{
                  position: 'absolute',
                  right: 0,
                  bottom: size * 0.08,
                  height: size * 0.12,
                  borderRadius: 99,
                  background: C.gold,
                  opacity: 0.35,
                  width: `${interpolate(frame, [12 + i * stagger, 30 + i * stagger], [0, 100], {
                    extrapolateLeft: 'clamp',
                    extrapolateRight: 'clamp',
                  })}%`,
                }}
              />
            )}
          </span>
        );
      })}
    </div>
  );
};

const Frame: React.FC<{children: React.ReactNode}> = ({children}) => {
  const {enter, exit} = useAnim();
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        padding: '60px 70px 150px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        gap: 36,
        fontFamily: FONT,
        color: C.text,
        opacity: Math.min(enter, exit),
        transform: `scale(${0.96 + 0.04 * enter})`,
      }}
    >
      {children}
    </div>
  );
};

const Heading: React.FC<{text: string; color?: string}> = ({text, color = C.green}) => {
  const {frame, fps} = useAnim();
  const p = pop(frame, fps, 0);
  return (
    <div
      style={{
        fontSize: 52,
        fontWeight: 800,
        color,
        direction: 'rtl',
        textAlign: 'center',
        opacity: p,
        transform: `translateY(${(1 - p) * -20}px)`,
      }}
    >
      {text}
    </div>
  );
};

const TitleScene: React.FC<{text: string; sub?: string}> = ({text, sub}) => {
  const {frame} = useAnim();
  return (
    <Frame>
      <Words text={text} size={82} weight={900} />
      {sub && (
        <div
          style={{
            fontSize: 38,
            color: C.muted,
            letterSpacing: 2,
            opacity: interpolate(frame, [15, 30], [0, 1], {extrapolateRight: 'clamp'}),
          }}
        >
          {sub}
        </div>
      )}
    </Frame>
  );
};

const hasArabic = (s: string) => /[؀-ۿ]/.test(s);

const StatScene: React.FC<Extract<Scene, {type: 'stat'}>> = ({value, decimals = 0, prefix = '', suffix = '', label}) => {
  const {frame, fps} = useAnim();
  const n = interpolate(frame, [0, fps * 1.3], [0, value], {
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.cubic),
  });
  const done = frame > fps * 1.3;
  const pulse = done ? 1 + 0.04 * Math.sin((frame - fps * 1.3) / 6) * Math.exp(-(frame - fps * 1.3) / 20) : 1;
  const lp = pop(frame, fps, 12);
  return (
    <Frame>
      <div
        style={{
          display: 'flex',
          alignItems: 'baseline',
          gap: 12,
          direction: hasArabic(prefix + suffix) ? 'rtl' : 'ltr',
          color: C.green,
          fontWeight: 900,
          transform: `scale(${pulse})`,
          textShadow: `0 0 60px ${C.green}55`,
        }}
      >
        {prefix && <span style={{fontSize: 90}}>{prefix}</span>}
        <span style={{fontSize: 230, lineHeight: 1}}>{n.toFixed(decimals)}</span>
        {suffix && <span style={{fontSize: 110}}>{suffix}</span>}
      </div>
      <div
        style={{
          fontSize: 50,
          fontWeight: 700,
          textAlign: 'center',
          direction: 'rtl',
          lineHeight: 1.45,
          opacity: lp,
          transform: `translateY(${(1 - lp) * 30}px)`,
        }}
      >
        {label}
      </div>
    </Frame>
  );
};

const CompareScene: React.FC<Extract<Scene, {type: 'compare'}>> = ({title, items}) => {
  const {frame, fps} = useAnim();
  const max = Math.max(...items.map((i) => i.value));
  return (
    <Frame>
      <Heading text={title} />
      <div style={{width: '100%', display: 'flex', flexDirection: 'column', gap: 40, direction: 'rtl'}}>
        {items.map((it, i) => {
          const p = spring({frame: frame - 10 - i * 12, fps, config: {damping: 200}, durationInFrames: 40});
          const color = it.highlight ? C.green : C.muted;
          return (
            <div key={i} style={{display: 'flex', flexDirection: 'column', gap: 12, opacity: Math.min(1, p * 2)}}>
              <div style={{fontSize: 42, fontWeight: 700}}>{it.label}</div>
              <div style={{display: 'flex', alignItems: 'center', gap: 20}}>
                <div
                  style={{
                    height: 70,
                    width: `${Math.max(4, (it.value / max) * 72 * p)}%`,
                    borderRadius: 16,
                    background: it.highlight
                      ? `linear-gradient(270deg, ${C.green}, #2BB57C)`
                      : `linear-gradient(270deg, #5E7C79, #46615E)`,
                    boxShadow: it.highlight ? `0 0 40px ${C.green}44` : 'none',
                  }}
                />
                <div style={{fontSize: 48, fontWeight: 900, color, whiteSpace: 'nowrap'}}>{it.display}</div>
              </div>
            </div>
          );
        })}
      </div>
    </Frame>
  );
};

const ListScene: React.FC<Extract<Scene, {type: 'list'}> & {total: number}> = ({title, items, total}) => {
  const {frame, fps} = useAnim();
  const step = Math.min(1.4, (total - 2) / items.length) * fps;
  return (
    <Frame>
      <Heading text={title} />
      <div style={{width: '100%', display: 'flex', flexDirection: 'column', gap: 28, direction: 'rtl'}}>
        {items.map((it, i) => {
          const p = pop(frame, fps, 8 + i * step);
          return (
            <div
              key={i}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 26,
                background: `${C.bg2}cc`,
                border: `2px solid ${C.green}33`,
                borderRadius: 26,
                padding: '22px 30px',
                opacity: Math.min(1, p * 1.5),
                transform: `translateX(${(1 - p) * -80}px)`,
              }}
            >
              <div
                style={{
                  minWidth: 70,
                  height: 70,
                  borderRadius: 99,
                  background: C.green,
                  color: C.bg,
                  fontSize: 40,
                  fontWeight: 900,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {i + 1}
              </div>
              <div style={{fontSize: 46, fontWeight: 700, lineHeight: 1.4}}>{it}</div>
            </div>
          );
        })}
      </div>
    </Frame>
  );
};

const PointScene: React.FC<{text: string; highlight?: string}> = ({text, highlight}) => (
  <Frame>
    <svg width="90" height="70" viewBox="0 0 90 70" style={{opacity: 0.5}}>
      <path d="M0 70V40Q0 10 30 0l6 10Q18 18 18 35h18v35zm50 0V40q0-30 30-40l6 10q-18 8-18 25h18v35z" fill={C.green} />
    </svg>
    <Words text={text} highlight={highlight} size={68} />
  </Frame>
);

const WarningScene: React.FC<{title: string; text: string}> = ({title, text}) => {
  const {frame, fps} = useAnim();
  const p = pop(frame, fps, 0);
  const shake = Math.sin(frame * 1.4) * 6 * Math.exp(-frame / 8);
  return (
    <Frame>
      <div
        style={{
          width: '100%',
          border: `4px solid ${C.red}`,
          borderRadius: 36,
          background: `${C.red}14`,
          padding: '50px 40px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 26,
          transform: `translateX(${shake}px)`,
        }}
      >
        <svg width="120" height="110" viewBox="0 0 120 110" style={{transform: `scale(${p})`}}>
          <path d="M60 6 114 102H6z" fill={C.red} stroke={C.red} strokeWidth="8" strokeLinejoin="round" />
          <rect x="54" y="36" width="12" height="36" rx="6" fill={C.bg} />
          <circle cx="60" cy="86" r="7" fill={C.bg} />
        </svg>
        <div style={{fontSize: 60, fontWeight: 900, color: C.red, direction: 'rtl'}}>{title}</div>
        <Words text={text} size={52} weight={700} stagger={2} />
      </div>
    </Frame>
  );
};

const Chip: React.FC<{text: string; p: number; gold?: boolean}> = ({text, p, gold}) => (
  <div
    style={{
      fontSize: gold ? 58 : 50,
      fontWeight: 900,
      padding: '18px 44px',
      borderRadius: 999,
      background: gold ? C.gold : `${C.bg2}`,
      color: gold ? C.bg : C.text,
      border: gold ? 'none' : `3px solid ${C.green}`,
      opacity: Math.min(1, p * 1.5),
      transform: `scale(${0.6 + 0.4 * p})`,
      direction: 'rtl',
      boxShadow: gold ? `0 0 60px ${C.gold}66` : 'none',
    }}
  >
    {text}
  </div>
);

const Sign: React.FC<{s: string; p: number}> = ({s, p}) => (
  <div style={{fontSize: 70, fontWeight: 900, color: C.green, opacity: p, lineHeight: 1}}>{s}</div>
);

const FormulaScene: React.FC<Extract<Scene, {type: 'formula'}> & {total: number}> = ({parts, result, total}) => {
  const {frame, fps} = useAnim();
  const step = Math.min(2.2, (total - 3) / (parts.length + 1)) * fps;
  return (
    <Frame>
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18}}>
        {parts.map((t, i) => (
          <React.Fragment key={i}>
            {i > 0 && <Sign s="+" p={pop(frame, fps, i * step - 4)} />}
            <Chip text={t} p={pop(frame, fps, i * step)} />
          </React.Fragment>
        ))}
        <Sign s="=" p={pop(frame, fps, parts.length * step - 4)} />
        <Chip text={result} gold p={pop(frame, fps, parts.length * step)} />
      </div>
    </Frame>
  );
};

const CtaScene: React.FC<{next: string}> = ({next}) => {
  const {frame, fps} = useAnim();
  const p = pop(frame, fps, 0);
  const pulse = 1 + 0.05 * Math.sin(frame / 5);
  return (
    <Frame>
      <div
        style={{
          fontSize: 76,
          fontWeight: 900,
          background: C.green,
          color: C.bg,
          padding: '22px 80px',
          borderRadius: 999,
          transform: `scale(${p * pulse})`,
          boxShadow: `0 0 80px ${C.green}66`,
        }}
      >
        تابعني
      </div>
      <Words text={next} size={54} weight={700} stagger={2} />
    </Frame>
  );
};

export const SceneView: React.FC<{scene: Scene}> = ({scene}) => {
  switch (scene.type) {
    case 'title':
      return <TitleScene text={scene.text} sub={scene.sub} />;
    case 'stat':
      return <StatScene {...scene} />;
    case 'compare':
      return <CompareScene {...scene} />;
    case 'list':
      return <ListScene {...scene} total={scene.dur} />;
    case 'point':
      return <PointScene text={scene.text} highlight={scene.highlight} />;
    case 'warning':
      return <WarningScene title={scene.title} text={scene.text} />;
    case 'formula':
      return <FormulaScene {...scene} total={scene.dur} />;
    case 'cta':
      return <CtaScene next={scene.next} />;
  }
};

export const SourceTag: React.FC<{source: string}> = ({source}) => {
  const {frame, durationInFrames} = useAnim();
  const o = interpolate(frame, [10, 25, durationInFrames - 10, durationInFrames], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <div
      style={{
        position: 'absolute',
        bottom: 50,
        left: 60,
        right: 60,
        textAlign: 'center',
        fontFamily: FONT,
        fontSize: 30,
        color: C.muted,
        opacity: o,
        direction: 'rtl',
      }}
    >
      المصدر: <bdi>{source}</bdi>
    </div>
  );
};
