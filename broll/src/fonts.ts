import { loadFont } from '@remotion/fonts';
import { staticFile } from 'remotion';
import { caption, font } from './tokens';

/**
 * The four families, self-hosted from `public/fonts`.
 *
 * Loading locally rather than from the Google Fonts CDN keeps renders
 * deterministic and offline-capable — a render never depends on a network
 * round-trip, and never silently falls back to a system face mid-frame.
 * Only the one weight each role actually uses is shipped.
 *
 * Importing this module for its side effect is enough; `src/Root.tsx` does it
 * once for every composition.
 */
const faces = [
  { role: font.display, file: 'AllertaStencil-Regular.woff2' },
  { role: font.ui, file: 'Rajdhani-SemiBold.woff2' },
  { role: font.mono, file: 'IBMPlexMono-Regular.woff2' },
  { role: font.body, file: 'IBMPlexSans-Regular.woff2' },
  { role: caption, file: 'Inter-ExtraBold.woff2' },
  /**
   * The slide formats need weight contrast to read as different formats: the
   * blurred set sets its paragraphs in regular and the textured set in
   * semibold, and the blurred set's step number is an italic. One family,
   * three more cuts.
   */
  { role: { fontFamily: 'Inter', fontWeight: 400 }, file: 'Inter-Regular.woff2' },
  { role: { fontFamily: 'Inter', fontWeight: 600 }, file: 'Inter-SemiBold.woff2' },
  {
    role: { fontFamily: 'Inter', fontWeight: 800 },
    file: 'Inter-ExtraBoldItalic.woff2',
    style: 'italic',
  },
  {
    role: { fontFamily: 'Inter', fontWeight: 400 },
    file: 'Inter-Italic.woff2',
    style: 'italic',
  },
  /** The one serif, for the title format's third line and nothing else. */
  { role: { fontFamily: 'Playfair Display', fontWeight: 700 },
    file: 'PlayfairDisplay-Bold.woff2' },
] as const;

export const fontsReady = Promise.all(
  faces.map((face) =>
    loadFont({
      family: face.role.fontFamily,
      url: staticFile(`fonts/${face.file}`),
      weight: String(face.role.fontWeight),
      style: 'style' in face ? face.style : 'normal',
    }),
  ),
);
