// Every scene has `at` (start, seconds), `dur` (seconds) and `say`
// (what you say on camera during that scene — also used to generate SCRIPTS.md).
type Base = {at: number; dur: number; say: string; source?: string};

export type Scene = Base &
  (
    | {type: 'title'; text: string; sub?: string}
    | {
        type: 'stat';
        value: number;
        decimals?: number;
        prefix?: string;
        suffix?: string;
        label: string;
      }
    | {
        type: 'compare';
        title: string;
        items: {label: string; value: number; display: string; highlight?: boolean}[];
      }
    | {type: 'list'; title: string; items: string[]}
    | {type: 'point'; text: string; highlight?: string}
    | {type: 'warning'; title: string; text: string}
    | {type: 'formula'; parts: string[]; result: string}
    | {type: 'cta'; next: string}
  );

export type Reel = {
  id: string; // also the expected video file name: public/videos/<id>.mp4
  number: number;
  title: string;
  goal: string;
  scenes: Scene[];
};
