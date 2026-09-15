import React, { memo } from 'react';
import { MathJax } from 'better-react-mathjax';
import { getImageUrl } from '../services/api';

const isBaaminiText = (str) => {
  if (!str || typeof str !== 'string') return false;
  // Baamini text patterns: semicolons inside words or common Baamini character sequences
  const baaminiPatterns = [
    /;[a-zA-Z0-9]/,      // Semicolon followed by letter (e.g. q;, k;, n;, d;)
    /[a-zA-Z];/,         // Letter followed by semicolon (e.g. hy;, W;, d;)
    /,lk;/,              // ,lk;
    /vd;w/,              // vd;w
    /nrhy;/,             // nrhy;
    /Kjd;/,              // Kjd;
    /Kjypy;/,            // Kjypy;
    /ngW/,               // ngW
    /Nky;/,              // Nky;
    /ghly;/,             // ghly;
    /rpj;jh;/,           // rpj;jh;
    /vdg;gL/,            // vdg;gL
    /jkpo;/,             // jkpo;
    /ehtyh;/             // ehtyh;
  ];
  return baaminiPatterns.some(pattern => pattern.test(str));
};

function MathText({ text, className = "", isTamil = false }) {
  if (!text) return null;
  
  const shouldApplyTamilFont = isTamil || isBaaminiText(text);
  const fontStyle = shouldApplyTamilFont ? { fontFamily: "'Bamini', 'Bamini Plain', 'Baamini', 'Baamini Plain', 'Mukta Malar', 'Latha', sans-serif" } : {};
  const fontClass = shouldApplyTamilFont ? 'tamil-font' : '';
  const combinedClass = `${className} ${fontClass}`.trim();

  // Check if text contains embedded <img ... /> tags
  const imgRegex = /<img\s+[^>]*src=["']([^"']+)["'][^>]*\/?>/gi;
  if (!imgRegex.test(text)) {
    return (
      <span className={combinedClass} style={{ display: 'inline-block', wordBreak: 'break-word', whiteSpace: 'normal', ...fontStyle }}>
        <MathJax 
          inline 
          dynamic 
          className={fontClass}
          style={fontStyle}
        >
          <span className={fontClass} style={fontStyle} dangerouslySetInnerHTML={{ __html: text }} />
        </MathJax>
      </span>
    );
  }

  // Parse text into segments of text and images
  const segments = [];
  let lastIndex = 0;
  imgRegex.lastIndex = 0;
  let match;

  while ((match = imgRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: 'text', content: text.substring(lastIndex, match.index) });
    }
    segments.push({ type: 'image', src: match[1] });
    lastIndex = imgRegex.lastIndex;
  }
  if (lastIndex < text.length) {
    segments.push({ type: 'text', content: text.substring(lastIndex) });
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
