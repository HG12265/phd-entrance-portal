import React, { memo } from 'react';
import { MathJax } from 'better-react-mathjax';
import { getImageUrl } from '../services/api';

function MathText({ text, className = "" }) {
  if (!text) return null;
  
  // Check if text contains embedded <img ... /> tags
  const imgRegex = /<img\s+[^>]*src=["']([^"']+)["'][^>]*\/?>/gi;
  if (!imgRegex.test(text)) {
    return (
      <MathJax 
        inline 
        dynamic 
        className={className}
        style={{ display: 'inline-block', wordBreak: 'break-word', whiteSpace: 'normal' }}
      >
        {text}
      </MathJax>
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
    <div className={className} style={{ display: 'inline-block', width: '100%' }}>
      {segments.map((seg, idx) => {
        if (seg.type === 'text') {
          if (!seg.content.trim()) return null;
          return (
            <MathJax 
              key={idx}
              inline 
              dynamic 
              style={{ display: 'inline-block', wordBreak: 'break-word', whiteSpace: 'normal' }}
            >
              {seg.content}
            </MathJax>
          );
        } else {
          const fullSrc = getImageUrl(seg.src);
          return (
            <div key={idx} style={{ margin: '0.5rem 0', textAlign: 'left' }}>
              <img 
                src={fullSrc} 
                alt="Cell Image" 
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
