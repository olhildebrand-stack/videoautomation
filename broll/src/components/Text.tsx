import React from 'react';
import { color, font, fontSize, monoFontSize, radius } from '../tokens';
import type { ColorToken, FontSizeToken } from '../tokens';

type TextProps = {
  children: React.ReactNode;
  /** Position on the brightness ladder. Hierarchy is brightness, never hue. */
  tone?: ColorToken;
  size?: FontSizeToken;
  style?: React.CSSProperties;
};

/** Headers only — two or three per frame at most. */
export const Display: React.FC<TextProps> = ({
  children,
  tone = 'flare',
  size = '4xl',
  style,
}) => (
  <div style={{ ...font.display, color: color[tone], fontSize: fontSize[size], ...style }}>
    {children}
  </div>
);

/** Anything actionable. */
export const UI: React.FC<TextProps> = ({
  children,
  tone = 'bone',
  size = 'lg',
  style,
}) => (
  <div style={{ ...font.ui, color: color[tone], fontSize: fontSize[size], ...style }}>
    {children}
  </div>
);

/**
 * Anything that names, counts, or labels. This is the layer that makes the
 * system read as instrumented rather than decorated — use it for anything
 * numeric. Restricted to 11–12px by its own size type.
 */
export const Mono: React.FC<
  Omit<TextProps, 'size'> & { size?: keyof typeof monoFontSize }
> = ({ children, tone = 'ash', size = 'sm', style }) => (
  <div style={{ ...font.mono, color: color[tone], fontSize: monoFontSize[size], ...style }}>
    {children}
  </div>
);

/** Running text only. Sentence case. */
export const Body: React.FC<TextProps> = ({
  children,
  tone = 'bone',
  size = 'xl',
  style,
}) => (
  <div style={{ ...font.body, color: color[tone], fontSize: fontSize[size], ...style }}>
    {children}
  </div>
);

/**
 * The one gesture: a solid flare fill with the text knocked out in void.
 *
 * `on` cross-fades the fill on the state tempo. Nothing scales, nothing glows,
 * nothing moves — the inversion is the entire beat.
 */
export const Inverted: React.FC<{
  children: React.ReactNode;
  /** 0 → 1 across the state change. */
  on: number;
  paddingBlock: number;
  paddingInline: number;
  style?: React.CSSProperties;
}> = ({ children, on, paddingBlock, paddingInline, style }) => (
  <div
    style={{
      position: 'relative',
      display: 'inline-block',
      paddingBlock,
      paddingInline,
      borderRadius: radius,
      ...style,
    }}
  >
    <div
      style={{
        position: 'absolute',
        inset: 0,
        backgroundColor: color.flare,
        opacity: on,
        borderRadius: radius,
      }}
    />
    <div style={{ position: 'relative' }}>{children}</div>
  </div>
);
