// ─── Cookie helpers ─────────────────────────────────────────────────────────
// Lee cookies no-HttpOnly desde document.cookie. Usado para el patrón
// double-submit CSRF (Fase 6.1): la cookie `sv_csrf` sí es legible por JS y
// debe reenviarse como header `X-CSRF-Token` en /auth/refresh/ y /auth/logout/.
// La cookie `sv_refresh` es HttpOnly y nunca es visible aquí — intencional.

export function getCookie(name: string): string | null {
  const match = document.cookie.match(
    new RegExp(`(?:^|; )${name.replace(/[.$?*|{}()[\]\\/+^]/g, '\\$&')}=([^;]*)`),
  )
  return match ? decodeURIComponent(match[1]) : null
}

export const CSRF_COOKIE_NAME = 'sv_csrf'
export const CSRF_HEADER_NAME = 'X-CSRF-Token'
