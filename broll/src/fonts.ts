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
] as const;

export const fontsReady = Promise.all(
  faces.map(({ role, file }) =>
    loadFont({
      family: role.fontFamily,
      url: staticFile(`fonts/${file}`),
      weight: String(role.fontWeight),
      style: 'normal',
    }),
  ),
);
