// Generates SCRIPTS.md from src/data/reels.ts (single source of truth).
// Run: node --experimental-strip-types gen-scripts.mjs
import {writeFileSync} from 'node:fs';
import {reels, reelDuration, SERIES_TITLE} from './src/data/reels.ts';

const mmss = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
const onScreen = (s) => {
  switch (s.type) {
    case 'title': return `عنوان كبير: «${s.text}»${s.sub ? ` + ${s.sub}` : ''}`;
    case 'stat': return `رقم بيعدّ: **${s.prefix ?? ''}${s.value}${s.suffix ?? ''}** — ${s.label}`;
    case 'compare': return `مقارنة بأعمدة: ${s.title} — ${s.items.map((i) => `${i.label}: ${i.display}`).join(' / ')}`;
    case 'list': return `قائمة بتظهر واحدة واحدة: ${s.title} — ${s.items.join('، ')}`;
    case 'point': return `جملة بتظهر كلمة كلمة: «${s.text}»`;
    case 'warning': return `كارت تحذير أحمر: ${s.title} — ${s.text}`;
    case 'formula': return `معادلة: ${s.parts.join(' + ')} = ${s.result}`;
    case 'cta': return `زرار «تابعني» + ${s.next}`;
  }
};

let md = `# سكريبتات ريلز: ${SERIES_TITLE}\n\n`;
md += `> الملف ده بيتولد تلقائي من \`src/data/reels.ts\`. لو عدّلت الكلام أو التوقيت هناك، شغّل \`npm run scripts\` عشان يتحدّث.\n\n`;
md += `## فكرة السلسلة\n\n`;
md += `${reels.length} ريلز قصيرة (حوالي 50–60 ثانية) بتبني المعنى خطوة خطوة: جسمك بيتعافى ← الأرقام ← **مكان كويس** ← **فكر كويس** ← **سلوك كويس** ← العلاقات والنوم ← امتى يبقى خطر ← ليه ناس بتتعافى وناس لأ. والحلقة الأخيرة بتمهد لحلقات **الحالات اللي اتشافت وازاي**.\n\n`;
md += `**الشكل:** إنت في النص اللي فوق من الشاشة بتتكلم، وتحت موشن جرافيكس بيظهر فيها الأرقام والجمل والمصادر في نفس اللحظة.\n\n`;
md += `### نصايح التصوير\n\n- صوّر **رأسي (9:16)** والكاميرا في مستوى عينك. خلّي وشك في **النص اللي فوق** من الكادر، لأن النص اللي تحت هيتغطى بالجرافيكس.\n- الكلام مكتوب بالعامية المصري. **قوله بطريقتك**؛ الأهم إن الترتيب والأرقام يفضلوا زي ما هم.\n- اسكت ثانية بين كل مشهد والتاني. ده بيسهّل ظبط التوقيت.\n- لو كلامك طلع أطول أو أقصر، التوقيتات بتتعدل بسهولة (شوف README).\n\n`;
md += `---\n\n`;
for (const r of reels) {
  md += `## الحلقة ${r.number}: ${r.title}\n\n`;
  md += `**الهدف:** ${r.goal}  \n**المدة:** حوالي ${reelDuration(r)} ثانية • **اسم ملف الفيديو:** \`public/videos/${r.id}.mp4\`\n\n`;
  md += `| الوقت | اللي هتقوله | اللي هيظهر على الشاشة | المصدر |\n|---|---|---|---|\n`;
  for (const s of r.scenes) {
    md += `| ${mmss(s.at)}–${mmss(s.at + s.dur)} | ${s.say} | ${onScreen(s)} | ${s.source ?? '—'} |\n`;
  }
  md += `\n**النص كامل للقراءة:**\n\n> ${r.scenes.map((s) => s.say).join(' ')}\n\n---\n\n`;
}
const sources = [...new Set(reels.flatMap((r) => r.scenes.map((s) => s.source).filter(Boolean)))];
md += `## كل المصادر المستخدمة\n\n${sources.map((s) => `- ${s}`).join('\n')}\n\n`;
md += `المراجع الكاملة موجودة في \`../research/self-recovery-research.md\` و \`../research/autoimmune-chronic-self-recovery.md\`.\n`;
writeFileSync(new URL('./SCRIPTS.md', import.meta.url), md);
console.log('SCRIPTS.md written');
