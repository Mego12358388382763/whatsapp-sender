import '@fontsource/cairo/400.css';
import '@fontsource/cairo/700.css';
import '@fontsource/cairo/800.css';
import '@fontsource/cairo/900.css';
import React from 'react';
import {Composition} from 'remotion';
import {reelDuration, reels} from './data/reels';
import {ReelComposition} from './Reel';
import {H, W} from './theme';

const FPS = 30;

export const RemotionRoot: React.FC = () => (
  <>
    {reels.map((reel) => (
      <Composition
        key={reel.id}
        id={reel.id}
        component={ReelComposition}
        durationInFrames={Math.round(reelDuration(reel) * FPS)}
        fps={FPS}
        width={W}
        height={H}
        defaultProps={{reel}}
      />
    ))}
  </>
);
