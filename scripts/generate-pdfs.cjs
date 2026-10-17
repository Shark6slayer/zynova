const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

// Simple, clean Markdown to HTML parser supporting headers, bold, code blocks, tables, and lists
function parseMarkdown(md) {
  let html = md;

  // Escape HTML entities inside inline text (except markdown syntax)
  // Code blocks ```...```
  html = html.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    const escaped = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return `<pre><code class="language-${lang}">${escaped}</code></pre>`;
  });

  // Inline code `...`
  html = html.replace(/`([^`]+)`/g, (match, code) => {
    const escaped = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return `<code>${escaped}</code>`;
  });

  // Headers
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

  // Bold & Italics
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  // Blockquotes
  html = html.replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>');

  // Horizontal Rules
  html = html.replace(/^---$/gim, '<hr/>');

  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');

  // Tables
  html = html.replace(/((?:\|[^\n]+\|\n?)+)/g, (match) => {
    const lines = match.trim().split('\n');
    if (lines.length < 2) return match;
    let tableHtml = '<table><thead>';
    const headerCols = lines[0].split('|').slice(1, -1);
    tableHtml += '<tr>' + headerCols.map(c => `<th>${c.trim()}</th>`).join('') + '</tr></thead><tbody>';

    for (let i = 2; i < lines.length; i++) {
      const cols = lines[i].split('|').slice(1, -1);
      tableHtml += '<tr>' + cols.map(c => `<td>${c.trim()}</td>`).join('') + '</tr>';
    }
    tableHtml += '</tbody></table>';
    return tableHtml;
  });

  // Unordered Lists
  html = html.replace(/^-\s+(.*$)/gim, '<ul><li>$1</li></ul>');
  html = html.replace(/<\/ul>\s*<ul>/g, ''); // merge lists

  // Ordered Lists
  html = html.replace(/^\d+\.\s+(.*$)/gim, '<ol><li>$1</li></ol>');
  html = html.replace(/<\/ol>\s*<ol>/g, ''); // merge lists

  // Paragraphs
  const blocks = html.split(/\n{2,}/);
  html = blocks.map(b => {
    b = b.trim();
    if (!b) return '';
    if (b.startsWith('<h') || b.startsWith('<pre') || b.startsWith('<table') || b.startsWith('<ul') || b.startsWith('<ol') || b.startsWith('<blockquote') || b.startsWith('<hr')) {
      return b;
    }
    return `<p>${b.replace(/\n/g, '<br/>')}</p>`;
  }).join('\n');

  return html;
}

const styledHtmlTemplate = (title, bodyContent) => `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>${title}</title>
  <style>
    @page {
      size: A4;
      margin: 20mm 15mm 20mm 15mm;
      @bottom-right {
        content: counter(page);
      }
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #1e293b;
      line-height: 1.6;
      font-size: 13px;
      margin: 0;
      padding: 0;
    }
    .header-banner {
      border-bottom: 2px solid #8b5cf6;
      padding-bottom: 12px;
      margin-bottom: 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .brand {
      font-size: 20px;
      font-weight: 800;
      color: #0f172a;
      letter-spacing: -0.5px;
    }
    .brand span {
      color: #8b5cf6;
    }
    .meta-tag {
      font-size: 11px;
      background: #f1f5f9;
      color: #475569;
      padding: 4px 8px;
      border-radius: 4px;
      font-weight: 600;
    }
    h1 {
      font-size: 22px;
      color: #0f172a;
      border-bottom: 1px solid #e2e8f0;
      padding-bottom: 8px;
      margin-top: 24px;
      page-break-after: avoid;
    }
    h2 {
      font-size: 16px;
      color: #334155;
      margin-top: 20px;
      border-bottom: 1px solid #f1f5f9;
      padding-bottom: 4px;
      page-break-after: avoid;
    }
    h3 {
      font-size: 14px;
      color: #475569;
      margin-top: 16px;
      page-break-after: avoid;
    }
    p, li {
      color: #334155;
    }
    code {
      font-family: "JetBrains Mono", Consolas, "Courier New", monospace;
      font-size: 11px;
      background: #f1f5f9;
      color: #0f172a;
      padding: 2px 5px;
      border-radius: 4px;
      border: 1px solid #e2e8f0;
    }
    pre {
      background: #0f172a;
      color: #f8fafc;
      padding: 12px;
      border-radius: 6px;
      overflow-x: auto;
      font-size: 11px;
      line-height: 1.45;
      page-break-inside: avoid;
    }
    pre code {
      background: transparent;
      color: #f8fafc;
      padding: 0;
      border: none;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0;
      font-size: 12px;
      page-break-inside: avoid;
    }
    th, td {
      border: 1px solid #cbd5e1;
      padding: 8px 10px;
      text-align: left;
    }
    th {
      background-color: #f8fafc;
      color: #0f172a;
      font-weight: 700;
    }
    tr:nth-child(even) {
      background-color: #f8fafc;
    }
    blockquote {
      border-left: 4px solid #8b5cf6;
      background: #f5f3ff;
      margin: 14px 0;
      padding: 8px 14px;
      color: #4c1d95;
      border-radius: 0 4px 4px 0;
    }
    hr {
      border: none;
      border-top: 1px solid #e2e8f0;
      margin: 24px 0;
    }
    .badge-pass {
      background: #dcfce7;
      color: #15803d;
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: bold;
    }
    .badge-fail {
      background: #fee2e2;
      color: #b91c1c;
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: bold;
    }
  </style>
</head>
<body>
  <div class="header-banner">
    <div class="brand">ZYNOVA <span>CLOUD</span></div>
    <div class="meta-tag">OFFICIAL TECHNICAL REPORT • 2026</div>
  </div>
  ${bodyContent}
</body>
</html>
`;

async function generatePdf(inputMdPath, outputPdfPath, title) {
  const mdContent = fs.readFileSync(inputMdPath, 'utf8');
  const parsedBody = parseMarkdown(mdContent);
  const fullHtml = styledHtmlTemplate(title, parsedBody);

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setContent(fullHtml, { waitUntil: 'networkidle' });
  await page.pdf({
    path: outputPdfPath,
    format: 'A4',
    margin: { top: '20mm', bottom: '20mm', left: '15mm', right: '15mm' },
    printBackground: true,
  });
  await browser.close();
  console.log(`Generated PDF: ${outputPdfPath}`);
}

(async () => {
  const outDir = 'C:/super_ai_docs';
  console.log('Beginning PDF report generation in ' + outDir + '...');

  // 1. ZYNOVA Complete Deployment Automation Master Report
  const depDocs = [
    '00_FINAL_STATUS.md',
    '01_PROJECT_AUDIT.md',
    '02_MONGODB_SETUP.md',
    '03_BACKEND_DEPLOYMENT.md',
    '04_DNS_HTTPS.md',
    '05_VERCEL_INTEGRATION.md',
    '06_TEST_RESULTS.md'
  ];
  let fullDeploymentMd = '';
  for (const doc of depDocs) {
    const p = path.join('C:/super_ai_docs/zynova_deployment', doc);
    if (fs.existsSync(p)) {
      fullDeploymentMd += fs.readFileSync(p, 'utf8') + '\n\n---\n\n';
    }
  }
  const mergedDepPath = path.join(outDir, 'temp_deployment_master.md');
  fs.writeFileSync(mergedDepPath, fullDeploymentMd, 'utf8');
  await generatePdf(mergedDepPath, path.join(outDir, 'ZYNOVA_CLOUD_DEPLOYMENT_REPORT.pdf'), 'Zynova Cloud Deployment Report');
  fs.unlinkSync(mergedDepPath);

  // 2. ZYNOVA Complete Audit Master Report
  const auditDocs = [
    '00_EXECUTIVE_SUMMARY.md',
    '01_AUDIT_SCOPE_AND_METHODOLOGY.md',
    '02_COMPLETE_FEATURE_TEST_MATRIX.md',
    '03_CONFIRMED_PROBLEMS.md',
    '04_SECURITY_AUDIT.md',
    '05_UI_UX_AND_ACCESSIBILITY.md',
    '06_FRONTEND_BACKEND_INTEGRATION.md',
    '07_PERFORMANCE_AND_RELIABILITY.md',
    '08_CODE_AND_CONFIGURATION_REVIEW.md',
    '09_PRIORITIZED_REMEDIATION_PLAN.md',
    '10_REGRESSION_TEST_PLAN.md',
    '11_UNTESTED_AREAS_AND_LIMITATIONS.md',
    '12_EVIDENCE_INDEX.md'
  ];
  let fullAuditMd = '';
  for (const doc of auditDocs) {
    const p = path.join('C:/super_ai_docs/zynova_audit', doc);
    if (fs.existsSync(p)) {
      fullAuditMd += fs.readFileSync(p, 'utf8') + '\n\n---\n\n';
    }
  }
  const mergedAuditPath = path.join(outDir, 'temp_audit_master.md');
  fs.writeFileSync(mergedAuditPath, fullAuditMd, 'utf8');
  await generatePdf(mergedAuditPath, path.join(outDir, 'ZYNOVA_WEBSITE_AUDIT_REPORT.pdf'), 'Zynova Complete Website Audit Report');
  fs.unlinkSync(mergedAuditPath);

  // 3. ZYNOVA Remediation & Verification Master Report
  const remDocs = [
    '00_REMEDIATION_SUMMARY.md',
    '01_FINDINGS_TO_FIX_MAPPING.md',
    '02_FILES_CHANGED.md',
    '03_TEST_RESULTS.md',
    '04_SECURITY_HEADER_VERIFICATION.md',
    '05_API_AND_DEPLOYMENT_STATUS.md',
    '06_REMAINING_BLOCKERS.md',
    '07_ROLLBACK_AND_RELEASE_CHECKLIST.md',
    '08_BEFORE_AFTER_METRICS.md'
  ];
  let fullRemMd = '';
  for (const doc of remDocs) {
    const p = path.join('C:/super_ai_docs/zynova_remediation', doc);
    if (fs.existsSync(p)) {
      fullRemMd += fs.readFileSync(p, 'utf8') + '\n\n---\n\n';
    }
  }
  const mergedRemPath = path.join(outDir, 'temp_remediation_master.md');
  fs.writeFileSync(mergedRemPath, fullRemMd, 'utf8');
  await generatePdf(mergedRemPath, path.join(outDir, 'ZYNOVA_REMEDIATION_REPORT.pdf'), 'Zynova Audit Remediation & Verification Report');
  fs.unlinkSync(mergedRemPath);

  console.log('All 3 comprehensive master PDF reports generated successfully!');
  process.exit(0);
})().catch(err => {
  console.error('Error generating PDF:', err);
  process.exit(1);
});
