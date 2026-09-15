import React, { memo } from 'react';
import { MathJax } from 'better-react-mathjax';
import { getImageUrl } from '../services/api';

const cleanBaaminiRomanNumerals = (str) => {
  if (!str || typeof str !== 'string') return str;
  // Auto-correct erroneous Baamini-to-Unicode conversion artifacts where 'i', 'ii', 'iii' became 'ை', 'ைை', 'ைைை'
  return str
    .replace(/(^|[\s(])ைைை([.\s,)\]]|$)/g, '$1iii$2')
    .replace(/(^|[\s(])ைை([.\s,)\]]|$)/g, '$1ii$2')
    .replace(/(^|[\s(])ை([.\s,)\]]|$)/g, '$1i$2')
    .replace(/\bைைை\s+மட்டும்/g, 'iii மட்டும்')
    .replace(/\bைை\s+மட்டும்/g, 'ii மட்டும்')
    .replace(/\bை\s+மட்டும்/g, 'i மட்டும்');
};

const isBaaminiText = (str) => {
  if (!str || typeof str !== 'string') return false;
  // Baamini Tamil font ASCII pattern detection:
  // 1. Any letter followed by semicolon (pulli in Baamini e.g., q;, k;, n;, d;, j;, r;, l;, t;, y;, s;, z;, h;)
  // 2. N or W followed by letter/symbol (e.g. Nj, Nk, W}, W;)
  // 3. Lowercase letter followed by capital H (e.g. pfH, feH, peH, juH)
  // 4. Specific Baamini root sequences (kzp, jp, rhp, rjh, Rth, Njr, i,ii)
  const baaminiPatterns = [
    /[a-zA-Z];/,            // Any letter followed by semicolon (100% unique to Baamini font!)
    /N[a-zA-Z]/,            // N followed by letter (e.g. Nj, Nk, Nu, Nd, Ng, Nr, Nt, Nf)
    /W[a-zA-Z}]/,           // W followed by letter or } (e.g. W}, W;)
    /[a-z]H/i,              // H at end of lowercase word or inside (e.g. pfH, feH)
    /kzp/,                  // kzp (மணி)
    /jp[a-z]/i,             // jp (தி)
    /rhp/i,                 // rhp (சரி)
    /rjh/i,                 // rjh (சதா)
    /Rth/i,                 // Rth (சுவா)
    /i,ii/i,                // i,ii pattern (i,ii,iii rhp)
    /,lk/i,                 // ,lk (இடம்)
    /,il/i,                 // ,il (இடை)
    /,i/i,                  // ,i
    /,]/i,                  // ,]
    /Fz/i,                  // Fz (குண)
    /ck/i,                  // ck (உம)
    /Fy/i,                  // Fy (குல)
    /Njr/i,                 // Njr (தேசிக)
    /Njrp/i,                // Njrp (தேசிக)
    /jpah/i                 // jpah (தியா)
  ];
  return baaminiPatterns.some(pattern => pattern.test(str));
};

function MathText({ text, className = "", isTamil = false }) {
  if (!text) return null;
  
  const isBaamini = isBaaminiText(text);
  const shouldApplyTamilFont = Boolean(isTamil || isBaamini);
  const processedText = shouldApplyTamilFont ? cleanBaaminiRomanNumerals(text) : text;
  const fontStyle = shouldApplyTamilFont ? { fontFamily: "'Bamini', 'Bamini Plain', 'Baamini', 'Baamini Plain', 'Mukta Malar', 'Latha', sans-serif" } : {};
  const fontClass = shouldApplyTamilFont ? 'tamil-font' : '';
  const combinedClass = `${className} ${fontClass}`.trim();

  // Check if text contains embedded <img ... /> tags
  const imgRegex = /<img\s+[^>]*src=["']([^"']+)["'][^>]*\/?>/gi;
  if (!imgRegex.test(processedText)) {
    return (
      <span className={combinedClass} style={{ display: 'inline-block', wordBreak: 'break-word', whiteSpace: 'normal', ...fontStyle }}>
        <MathJax 
          inline 
          dynamic 
          className={fontClass}
          style={fontStyle}
        >
          <span className={fontClass} style={fontStyle} dangerouslySetInnerHTML={{ __html: processedText }} />
        </MathJax>
      </span>
    );
  }

  // Parse text into segments of text and images
  const segments = [];
  let lastIndex = 0;
  imgRegex.lastIndex = 0;
  let match;

  while ((match = imgRegex.exec(processedText)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: 'text', content: processedText.substring(lastIndex, match.index) });
    }
    segments.push({ type: 'image', src: match[1] });
    lastIndex = imgRegex.lastIndex;
  }
  if (lastIndex < processedText.length) {
    segments.push({ type: 'text', content: processedText.substring(lastIndex) });
  }

  return (
    <div className={combinedClass} style={{ display: 'inline-block', width: '100%', ...fontStyle }}>
      {segments.map((seg, idx) => {
        if (seg.type === 'text') {
          if (!seg.content.trim()) return null;
          return (
            <span key={idx} className={fontClass} style={{ display: 'inline-block', wordBreak: 'break-word', whiteSpace: 'normal', ...fontStyle }}>
              <MathJax 
                inline 
                dynamic 
                className={fontClass}
                style={fontStyle}
              >
                <span className={fontClass} style={fontStyle} dangerouslySetInnerHTML={{ __html: seg.content }} />
              </MathJax>
            </span>
          );
        } else {
          const fullSrc = getImageUrl(seg.src);
          return (
            <div key={idx} style={{ margin: '0.5rem 0', textAlign: 'left' }}>
              <img 
                src={fullSrc} 
                alt="Question Diagram" 
                style={{ 
                  maxWidth: '100%', 
                  maxHeight: '260px', 
                  objectFit: 'contain', 
                  borderRadius: '0.375rem', 
                  border: 'none',
                  padding: '0',
                  display: 'inline-block'
                }} 
                onError={(e) => {
                  e.target.src = seg.src;
                }}
              />
            </div>
          );
        }
      })}
    </div>
  );
}

export default memo(MathText);



