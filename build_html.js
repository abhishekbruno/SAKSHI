const fs = require('fs');
const path = require('path');

const mdPath = path.join(__dirname, 'SAKSHI_SYSTEM_ARCHITECTURE.md');
const mdContent = fs.readFileSync(mdPath, 'utf8');

const htmlTemplate = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SAKSHI: Master Architecture & Engineering Specification</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <style>
    :root {
      --bg: #090d16;
      --surface: #111827;
      --surface-border: #1f2937;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --primary: #38bdf8;
      --primary-glow: rgba(56, 189, 248, 0.15);
      --accent: #818cf8;
      --success: #34d399;
      --danger: #f87171;
      --code-bg: #0d1117;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.7;
      font-size: 16px;
      padding-bottom: 80px;
    }

    header {
      background: rgba(17, 24, 39, 0.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--surface-border);
      position: sticky;
      top: 0;
      z-index: 100;
      padding: 16px 32px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .brand-badge {
      background: linear-gradient(135deg, #0284c7, #6366f1);
      color: #fff;
      font-weight: 800;
      font-size: 13px;
      padding: 4px 10px;
      border-radius: 6px;
      letter-spacing: 1px;
    }

    .brand-title {
      font-size: 16px;
      font-weight: 700;
      color: #fff;
      letter-spacing: -0.3px;
    }

    .actions {
      display: flex;
      gap: 12px;
    }

    .btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: var(--surface);
      color: var(--text);
      border: 1px solid var(--surface-border);
      padding: 8px 16px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.2s ease;
    }

    .btn:hover {
      background: #1f2937;
      border-color: var(--primary);
      color: var(--primary);
      transform: translateY(-1px);
    }

    .btn-primary {
      background: #0284c7;
      border-color: #38bdf8;
      color: #fff;
    }

    .btn-primary:hover {
      background: #0369a1;
      color: #fff;
    }

    .container {
      max-width: 1100px;
      margin: 40px auto;
      padding: 0 24px;
    }

    #content {
      background: var(--surface);
      border: 1px solid var(--surface-border);
      border-radius: 16px;
      padding: 48px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    }

    h1, h2, h3, h4, h5, h6 {
      color: #ffffff;
      font-weight: 700;
      margin-top: 36px;
      margin-bottom: 16px;
      line-height: 1.3;
      letter-spacing: -0.4px;
    }

    h1 {
      font-size: 32px;
      border-bottom: 1px solid var(--surface-border);
      padding-bottom: 12px;
      color: #38bdf8;
    }

    h2 {
      font-size: 24px;
      border-bottom: 1px solid rgba(255,255,255,0.08);
      padding-bottom: 8px;
      color: #e0e7ff;
    }

    h3 {
      font-size: 19px;
      color: #93c5fd;
    }

    p {
      margin-bottom: 18px;
      color: #d1d5db;
    }

    ul, ol {
      margin-left: 28px;
      margin-bottom: 20px;
      color: #d1d5db;
    }

    li {
      margin-bottom: 6px;
    }

    blockquote {
      border-left: 4px solid var(--primary);
      background: var(--primary-glow);
      padding: 16px 20px;
      border-radius: 0 8px 8px 0;
      margin: 24px 0;
      font-style: normal;
      color: #e2e8f0;
    }

    blockquote strong {
      color: #38bdf8;
    }

    code {
      font-family: 'JetBrains Mono', monospace;
      font-size: 14px;
      background: var(--code-bg);
      color: #38bdf8;
      padding: 2px 6px;
      border-radius: 4px;
      border: 1px solid #1e293b;
    }

    pre {
      background: var(--code-bg);
      border: 1px solid var(--surface-border);
      border-radius: 10px;
      padding: 18px;
      overflow-x: auto;
      margin: 24px 0;
    }

    pre code {
      background: none;
      padding: 0;
      border: none;
      color: #e2e8f0;
      font-size: 13.5px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      margin: 28px 0;
      font-size: 14.5px;
    }

    th, td {
      border: 1px solid var(--surface-border);
      padding: 12px 14px;
      text-align: left;
    }

    th {
      background: #1e293b;
      color: #38bdf8;
      font-weight: 600;
    }

    tr:nth-child(even) {
      background: rgba(255, 255, 255, 0.02);
    }

    tr:hover {
      background: rgba(56, 189, 248, 0.04);
    }

    .mermaid {
      background: #0d1117;
      border: 1px solid #1e293b;
      border-radius: 12px;
      padding: 24px;
      margin: 28px 0;
      text-align: center;
      overflow-x: auto;
    }

    hr {
      border: none;
      border-top: 1px solid var(--surface-border);
      margin: 40px 0;
    }

    @media print {
      body {
        background: #fff;
        color: #000;
      }
      header {
        display: none;
      }
      #content {
        border: none;
        box-shadow: none;
        padding: 0;
        background: #fff;
        color: #000;
      }
      h1, h2, h3, h4 {
        color: #000;
      }
      p, li {
        color: #333;
      }
      th {
        background: #eee;
        color: #000;
      }
      td, th {
        border: 1px solid #ccc;
      }
      .mermaid {
        background: #fff;
        border: 1px solid #ccc;
      }
      pre {
        background: #f8f8f8;
        border: 1px solid #ddd;
        color: #000;
      }
      code {
        color: #000;
        background: #f0f0f0;
      }
    }
  </style>
</head>
<body>

  <header>
    <div class="brand">
      <span class="brand-badge">SAKSHI ARCHITECTURE</span>
      <span class="brand-title">Death Investigation Reasoning Agent</span>
    </div>
    <div class="actions">
      <button class="btn" onclick="window.print()">🖨️ Print / Save as PDF</button>
      <button class="btn btn-primary" id="downloadMdBtn">⬇️ Download Markdown</button>
    </div>
  </header>

  <div class="container">
    <article id="content">Loading documentation...</article>
  </div>

  <script id="markdown-raw" type="text/plain">${mdContent.replace(/<\/script>/g, '<\\/script>')}</script>

  <script>
    mermaid.initialize({
      startOnLoad: false,
      theme: 'dark',
      securityLevel: 'loose',
      fontFamily: 'Inter, sans-serif',
      themeVariables: {
        darkMode: true,
        background: '#0d1117',
        primaryColor: '#1e293b',
        primaryBorderColor: '#38bdf8',
        primaryTextColor: '#ffffff',
        lineColor: '#60a5fa',
        edgeLabelBackground: '#1e293b'
      }
    });

    const rawMd = document.getElementById('markdown-raw').textContent;

    // Custom renderer for marked to treat \`\`\`mermaid code blocks as <div class="mermaid">
    const renderer = new marked.Renderer();
    const originalCode = renderer.code.bind(renderer);

    renderer.code = function(code, language) {
      if (language === 'mermaid') {
        return '<div class="mermaid">' + code + '</div>';
      }
      return originalCode(code, language);
    };

    marked.setOptions({
      renderer: renderer,
      breaks: false,
      gfm: true
    });

    document.getElementById('content').innerHTML = marked.parse(rawMd);

    // Render Mermaid diagrams
    mermaid.run({
      querySelector: '.mermaid'
    });

    // Download MD functionality
    document.getElementById('downloadMdBtn').addEventListener('click', () => {
      const blob = new Blob([rawMd], { type: 'text/markdown;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'SAKSHI_SYSTEM_ARCHITECTURE.md';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    });
  </script>
</body>
</html>
`;

const htmlPath = path.join(__dirname, 'SAKSHI_SYSTEM_ARCHITECTURE.html');
fs.writeFileSync(htmlPath, htmlTemplate, 'utf8');

// Also copy to artifacts directory
const artifactDir = 'C:\\Users\\zone\\.gemini\\antigravity-ide\\brain\\ea280381-cf0d-4886-a761-27d5910d2f14';
fs.writeFileSync(path.join(artifactDir, 'SAKSHI_SYSTEM_ARCHITECTURE.html'), htmlTemplate, 'utf8');

console.log('HTML build completed successfully at ' + htmlPath);
