export function escapeHtml(value) {
  return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;')
}

export function csvCell(value) {
  let text = String(value ?? '')
  // Quoting alone does not prevent spreadsheet formula execution.
  if (/^[\s\uFEFF]*[=+\-@]/u.test(text) || /^[\t\r\n]/.test(text)) text = "'" + text
  return '"' + text.replaceAll('"', '""') + '"'
}

export function renderCsv(report) {
  const columns = ['system', 'case_id', 'family', 'locale', 'partition', 'tags', 'expected_urgency',
    'actual_urgency', 'urgency_match', 'policy_pass', 'required_rule_ids', 'actual_rule_ids', 'problems', 'turns']
  const rows = Object.entries(report.systems).flatMap(([system, result]) => result.rows.map(row => [
    system, row.id, row.family, row.locale, row.split, row.tags.join('|'), row.expected.urgency,
    row.actual.urgency ?? 'error', row.urgency_match, row.policy_pass,
    row.expected.rule_ids.join('|'), row.actual.rule_ids.join('|'), row.problems.join('; '), JSON.stringify(row.turns)
  ]))
  return '\uFEFF' + [columns, ...rows].map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n'
}

const percent = value => value === null ? 'n/a' : `${(value * 100).toFixed(1)}%`
const ratio = metric => `${metric.numerator}/${metric.denominator} (${percent(metric.value)})`

export function renderMarkdown(report) {
  const full = report.systems.full.summaries['all/all']
  const lines = [
    '# Eye policy research benchmark', '',
    '**Synthetic development fixtures; draft author labels and translations. These results are not clinical accuracy, external validation, or evidence of safety. Unknown is not a negative clinical finding.**', '',
    `Generated: ${report.manifest.generated_at}. Dataset: ${report.manifest.dataset_version}.`, '',
    `${full.cases} cases, ${full.families} scenario families, three locales. Evaluation partitions are public development fixtures, not a blinded test set.`, '',
    '| System | Urgency agreement | Policy conformance | Emergency-level recall | Unexpected escalation on expected-unknown cases | Errors |',
    '| --- | --- | --- | --- | --- | --- |'
  ]
  for (const [system, result] of Object.entries(report.systems)) {
    const m = result.summaries['all/all']
    lines.push(`| ${system} | ${ratio(m.urgency_agreement)} | ${ratio(m.policy_conformance)} | ${ratio(m.emergency_level_recall)} | ${ratio(m.unexpected_escalation)} | ${m.errors} |`)
  }
  lines.push('', '## Production engine by locale', '', '| Locale | Cases | Urgency agreement | Policy conformance |', '| --- | --- | --- | --- |')
  for (const locale of report.manifest.locales) {
    const m = report.systems.full.summaries[`${locale}/all`]
    lines.push(`| ${locale} | ${m.cases} | ${ratio(m.urgency_agreement)} | ${ratio(m.policy_conformance)} |`)
  }
  const interval = full.family_macro_agreement
  lines.push('', `Family-macro urgency agreement: ${percent(interval.estimate)}; descriptive 95% family-bootstrap interval ${percent(interval.lower)} to ${percent(interval.upper)} (${interval.clusters} families; ${interval.resamples} resamples; seed ${report.manifest.seed}). These intervals resample authored families, not patients.`, '',
    '## Paired ablations', '', 'These remove one capability from the same engine. They are not independent diagnostic systems or comparisons with clinicians.', '',
    '| Comparison | Full-only matches | Ablation-only matches | Family-macro agreement difference (95% descriptive interval) |', '| --- | --- | --- | --- |')
  for (const [system, groups] of Object.entries(report.comparisons)) {
    const comparison = groups['all/all'], ci = comparison.family_macro_agreement_difference
    lines.push(`| full minus ${system} | ${comparison.full_only_matches} | ${comparison.baseline_only_matches} | ${percent(ci.estimate)} (${percent(ci.lower)} to ${percent(ci.upper)}) |`)
  }
  lines.push('', '## Production disagreements', '')
  const failures = report.systems.full.rows.filter(row => !row.policy_pass)
  if (!failures.length) lines.push('No disagreements with the supplied draft expectations. This does not establish clinical performance.')
  for (const row of failures) lines.push(`- **${row.id}**: expected ${row.expected.urgency}, received ${row.actual.urgency ?? 'error'}. ${row.problems.join('; ')}.`)
  lines.push('', '## Coverage and reproducibility', '',
    `Observed production rule activations: ${report.coverage.observed_production_rule_ids.length}/${report.coverage.all_rule_ids.length}. Unactivated rules: ${report.coverage.unactivated_rule_ids.join(', ') || 'none'}. Activating a rule does not measure its clinical correctness.`, '',
    `Dataset SHA-256: \`${report.manifest.dataset_sha256}\``, '',
    `Bundled production engine SHA-256: \`${report.manifest.engine_bundle_sha256}\``, '',
    `Node: ${report.manifest.runtime.node}; platform: ${report.manifest.runtime.platform}/${report.manifest.runtime.arch}. No server, credentials, network requests or model calls were used.`, '',
    'The JSON contains input hashes, per-turn traces, exact denominators, confusion matrices, subgroup results and paired comparisons. The CSV contains one row per case/system. The HTML provides local interactive filtering.', '',
    `See [the research protocol](<${report.manifest.protocol_relative_path || '../../README.md'}>) for interpretation, partitioning, limitations, and the proposed independent study.`, '')
  return lines.join('\n')
}

export function renderHtml(report) {
  const payload = JSON.stringify(report).replaceAll('<', '\\u003c').replaceAll('\u2028', '\\u2028').replaceAll('\u2029', '\\u2029')
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>HumanTwin · Research benchmark</title>
<style>
:root{font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#193247;background:#edf3f6;line-height:1.55;font-synthesis:none}*{box-sizing:border-box}body{margin:0}header{background:#102e42;color:#fff;padding:38px max(24px,calc((100vw - 1240px)/2)) 32px}header p{color:#c2d8e5;max-width:850px}h1{font-size:clamp(26px,4vw,39px);line-height:1.2;margin:10px 0}h2{font-size:20px}.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.16em;color:#8de0cf}main{max-width:1288px;margin:auto;padding:24px}.notice{border-left:4px solid #c06b1c;background:#fff5e7;padding:16px 20px;margin-bottom:24px}.toolbar{display:flex;gap:14px;flex-wrap:wrap;align-items:end;margin:24px 0}label{display:grid;gap:5px;font-size:13px;font-weight:600}select,input{padding:10px;border:1px solid #bbccd8;border-radius:7px;background:white;max-width:100%;color:#193247}input{min-width:230px}.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.card,.panel{background:white;border:1px solid #d9e4eb;border-radius:10px;padding:20px}.card strong{display:block;font-size:29px;color:#136c62;margin-top:8px}.card small{color:#5b6f7e}.panel{margin-top:18px;min-width:0}.muted{color:#526978;font-size:13px}.tables{display:grid;grid-template-columns:1fr 1fr;gap:18px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;text-align:left;font-size:13px}th,td{border-bottom:1px solid #e0e8ed;padding:11px;vertical-align:top}th{font-weight:600;background:#f3f7f9}td code{overflow-wrap:anywhere}details{margin:4px 0}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;line-height:1.5;background:#f2f6f8;padding:12px;border-radius:6px;max-width:640px}.badge{display:inline-block;font-size:11px;font-weight:650;padding:3px 8px;border-radius:20px;background:#dff4e9;color:#185c3b}.badge.fail{background:#ffebe7;color:#9c3223}a{color:#14685e}code{font-size:12px;word-break:break-word}.footnote{font-size:12px;color:#607280;margin-top:24px}.no-js{background:#fff5e7;padding:16px}@media(max-width:850px){.cards{grid-template-columns:repeat(2,1fr)}.tables{grid-template-columns:1fr}main{padding:16px}}@media(max-width:480px){.cards{grid-template-columns:1fr}select,input{width:100%}.toolbar label{width:100%}}
</style></head><body>
<header><div class="eyebrow">HumanTwin / Research instrumentation</div><h1>Eye policy benchmark</h1><p>Explore multilingual symptom intake, retained conversation context and explicit policy disagreements. Every result is traceable to a synthetic scenario.</p><div id="version" class="eyebrow"></div></header>
<main><div class="notice"><strong>Draft synthetic evaluation — clinical use remains disabled.</strong><br>Author labels and Arabic/Sorani translations have not been independently reviewed. Agreement measures conformance to these draft expectations. It does not measure diagnostic accuracy or patient safety. “Unknown” means urgency is not established.</div>
<noscript><p class="no-js">Enable JavaScript to explore this offline report, or open report.md, report.json or cases.csv beside this file.</p></noscript>
<div class="toolbar"><label>System<select id="system"><option value="full">Full production engine</option><option value="latest_turn_only">Ablation: latest turn only</option><option value="structured_only">Ablation: structured inputs only</option></select></label><label>Language<select id="locale"><option value="all">All three languages</option><option value="en">English</option><option value="ar-IQ">Iraqi Arabic (draft)</option><option value="ckb">Sorani (draft)</option></select></label><label>Partition<select id="split"><option value="all">All public fixtures</option><option value="development">Development</option><option value="evaluation">Evaluation (public, exploratory)</option></select></label></div>
<p id="description" class="muted"></p><div class="cards" id="cards"></div><p class="muted" id="interval"></p>
<div class="tables"><section class="panel"><h2>Urgency confusion matrix</h2><p class="muted">Rows: draft expectation. Columns: observed output.</p><div class="scroll" id="confusion"></div></section><section class="panel"><h2>Effect of removing a capability</h2><p class="muted">Full minus ablation; paired scenario families. These are software ablations of the same engine.</p><div class="scroll" id="comparisons"></div></section></div>
<section class="panel"><h2>Scenario explorer</h2><p class="muted">The following filters affect the case table only. Open a row for exact inputs, activated rules and turn-by-turn checkpoints.</p><div class="toolbar"><label>Outcome<select id="outcome"><option value="all">All cases</option><option value="fail">Policy disagreements</option><option value="pass">Policy matches</option></select></label><label>Find a scenario<input id="search" type="search" placeholder="Family, tag or symptom text"></label></div><p id="count" class="muted" aria-live="polite"></p><div class="scroll"><table><thead><tr><th>Scenario / inputs</th><th>Language</th><th>Expected</th><th>Observed</th><th>Policy</th></tr></thead><tbody id="rows"></tbody></table></div></section>
<section class="panel"><h2>Reproducibility and limits</h2><div id="manifest"></div><p class="muted">The seed controls resampling. Translations stay together when partitioning and bootstrapping scenario families. Intervals describe these authored fixtures and do not quantify uncertainty in patient populations. The publicly visible evaluation partition is not a blinded test set. Browser engine results do not validate independent PHP replay, the Python assistant, the 3D anatomy, or a paid AI model.</p><p><a href="report.json" download>JSON and traces</a> · <a href="cases.csv" download>CSV</a> · <a href="report.md">Markdown report</a></p></section>
<p class="footnote">Generated locally. No external scripts, fonts, analytics, network requests or model calls. Reporting approach informed by <a href="https://www.nature.com/articles/s41591-024-03425-5">TRIPOD-LLM</a>; no compliance or validation claim is made.</p>
</main><script type="application/json" id="benchmark-data">${payload}</script><script>
${browserScript}
</script></body></html>`
}

const browserScript = String.raw`
const report = JSON.parse(document.getElementById('benchmark-data').textContent);
const el = id => document.getElementById(id);
const escape = value => String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const pct = value => value === null ? 'n/a' : (value * 100).toFixed(1) + '%';
const count = metric => metric.numerator + '/' + metric.denominator;
function render() {
  const system = el('system').value, locale = el('locale').value, split = el('split').value;
  const key = locale + '/' + split;
  const result = report.systems[system], metrics = result.summaries[key];
  el('description').textContent = result.description;
  const cards = [['Urgency agreement',metrics.urgency_agreement],['Policy conformance',metrics.policy_conformance],['Emergency-level recall',metrics.emergency_level_recall],['Unexpected escalation',metrics.unexpected_escalation]];
  el('cards').innerHTML = cards.map(([title,metric]) => '<div class="card">' + title + '<strong>' + pct(metric.value) + '</strong><small>' + count(metric) + ' cases</small></div>').join('');
  const ci = metrics.family_macro_agreement;
  el('interval').textContent = metrics.cases + ' cases · ' + metrics.families + ' families · ' + metrics.errors + ' errors · family-macro agreement ' + pct(ci.estimate) + ' (95% descriptive family-bootstrap interval ' + pct(ci.lower) + ' to ' + pct(ci.upper) + '). Emergency recall includes expected-emergency cases only; unexpected escalation includes expected-unknown cases only.';
  const levels = ['unknown','urgent','emergency'];
  el('confusion').innerHTML = '<table><thead><tr><th>Expected</th>' + [...levels,'error'].map(level => '<th>' + level + '</th>').join('') + '</tr></thead><tbody>' + levels.map(level => '<tr><th>' + level + '</th>' + [...levels,'error'].map(actual => '<td>' + metrics.confusion[level][actual] + '</td>').join('') + '</tr>').join('') + '</tbody></table>';
  el('comparisons').innerHTML = '<table><thead><tr><th>Ablation</th><th>Difference</th><th>95% interval</th></tr></thead><tbody>' + Object.entries(report.comparisons).map(([name,groups]) => {
    const ci = groups[key].family_macro_agreement_difference;
    return '<tr><td>' + name.replaceAll('_',' ') + '</td><td>' + pct(ci.estimate) + '</td><td>' + pct(ci.lower) + ' to ' + pct(ci.upper) + '</td></tr>';
  }).join('') + '</tbody></table>';
  const outcome = el('outcome').value, search = el('search').value.toLocaleLowerCase();
  const rows = result.rows.filter(row => (locale === 'all' || row.locale === locale) && (split === 'all' || row.split === split) && (outcome === 'all' || row.policy_pass === (outcome === 'pass')) && (!search || JSON.stringify([row.id,row.tags,row.turns]).toLocaleLowerCase().includes(search)));
  el('count').textContent = rows.length + ' matching cases';
  el('rows').innerHTML = rows.map(row => '<tr><td><details><summary>' + escape(row.family) + '</summary><p>' + escape(row.intent) + '</p><p class="muted">' + escape(row.tags.join(' · ')) + '</p><strong>Policy disagreements</strong><pre>' + escape(row.problems.length ? row.problems.join('\n') : 'None against the supplied draft expectation.') + '</pre><strong>Expected state / required rules</strong><pre>' + escape(JSON.stringify(row.expected,null,2)) + '</pre><strong>Turn trace</strong><pre dir="auto">' + escape(JSON.stringify(row.trace,null,2)) + '</pre><strong>Final reported state</strong><pre dir="auto">' + escape(JSON.stringify(row.actual,null,2)) + '</pre></details></td><td>' + escape(row.locale) + '</td><td>' + escape(row.expected.urgency) + '</td><td>' + escape(row.actual.urgency ?? 'error') + '</td><td><span class="badge' + (row.policy_pass ? '' : ' fail') + '">' + (row.policy_pass ? 'match' : 'disagrees') + '</span></td></tr>').join('');
}
el('version').textContent = report.manifest.dataset_version + ' · ' + report.manifest.rules_version;
el('manifest').innerHTML = '<p><strong>' + report.coverage.observed_production_rule_ids.length + '/' + report.coverage.all_rule_ids.length + '</strong> policy rules activated by the production engine. Not activated: ' + escape(report.coverage.unactivated_rule_ids.join(', ') || 'none') + '.</p><p class="muted">Run: ' + escape(report.manifest.generated_at) + ' · Node ' + escape(report.manifest.runtime.node) + ' · seed ' + report.manifest.seed + ' · ' + report.manifest.resamples + ' resamples</p><p class="muted">Dataset SHA-256<br><code>' + escape(report.manifest.dataset_sha256) + '</code></p><p class="muted">Production engine bundle SHA-256<br><code>' + escape(report.manifest.engine_bundle_sha256) + '</code></p>';
for (const id of ['system','locale','split','outcome']) el(id).addEventListener('change',render);
el('search').addEventListener('input',render);
render();
`
