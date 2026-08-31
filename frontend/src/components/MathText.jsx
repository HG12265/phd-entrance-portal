import React, { memo } from 'react';
import { MathJax } from 'better-react-mathjax';
import { getImageUrl } from '../services/api';

/**
 * MathText — Renders mixed text content that may include:
 * - Plain text
 * - LaTeX equations (rendered by MathJax)
 * - Embedded <img> HTML tags (question images, EMF/WMF converted to PNG)
 *
 * Handles:
 * - src attributes with relative paths → prefixed with backend base URL
 * - data-format attribute for debugging (shows original format in alt text)
 * - Graceful image error fallback (shows [Image] label instead of broken icon)
 */
function MathText({ text, className = "" }) {
  if (!text) return null;

  // Parse embedded <img> tags from text
  const imgRegex = /<img\s+[^>]*src=["']([^"']+)["'][^>]*\/?>/gi;
  const hasImages = imgRegex.test(text);
  imgRegex.lastIndex = 0;

  if (!hasImages) {
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

  // Parse text into segments: text blocks and image blocks
  const segments = [];
  let lastIndex = 0;

  // Full img tag regex to capture all attributes
  const fullImgRegex = /<img\s+([^>]*)\/?\s*>/gi;
  let match;
  while ((match = fullImgRegex.exec(text)) !== null) {
    // Text before this image
    if (match.index > lastIndex) {
      segments.push({ type: 'text', content: text.substring(lastIndex, match.index) });
    }

    // Parse attributes from the img tag
    const attrsStr = match[1];
    const srcMatch = /src=["']([^"']+)["']/.exec(attrsStr);
    const altMatch = /alt=["']([^"']*)["']/.exec(attrsStr);
    const fmtMatch = /data-format=["']([^"']*)["']/.exec(attrsStr);

    segments.push({
      type: 'image',
      src: srcMatch ? srcMatch[1] : '',
      alt: altMatch ? altMatch[1] : 'Question image',
      format: fmtMatch ? fmtMatch[1] : '',
    });

    lastIndex = fullImgRegex.lastIndex;
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
          const altLabel = seg.format
            ? `${seg.alt} (${seg.format.toUpperCase()})`
            : seg.alt;

          return (
            <div key={idx} style={{ margin: '0.5rem 0', textAlign: 'left' }}>
              <img
                src={fullSrc}
                alt={altLabel}
                data-original-format={seg.format || undefined}
                style={{
                  maxWidth: '100%',
                  maxHeight: '280px',
                  objectFit: 'contain',
                  borderRadius: '0.375rem',
                  border: 'none',
                  padding: '0',
                  display: 'inline-block',
                  verticalAlign: 'middle',
                }}
                onError={(e) => {
                  // Replace broken image with a styled placeholder text
                  const parent = e.target.parentNode;
                  if (parent && !parent.dataset.errorHandled) {
                    parent.dataset.errorHandled = '1';
                    const placeholder = document.createElement('span');
                    placeholder.style.cssText = [
                      'display:inline-block',
                      'padding:0.25rem 0.75rem',
                      'background:#f1f5f9',
                      'border:1px solid #e2e8f0',
                      'border-radius:4px',
                      'font-size:0.8rem',
                      'color:#64748b',
                      'font-style:italic',
                    ].join(';');
                    placeholder.textContent = `[${seg.format ? seg.format.toUpperCase() + ' ' : ''}Image]`;
                    parent.replaceChild(placeholder, e.target);
                  }
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
