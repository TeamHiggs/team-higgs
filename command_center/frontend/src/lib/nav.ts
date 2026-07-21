// Send an expired session back through the OIDC flow. Isolated here so it is the
// one place a full-page navigation happens (and easy to stub in tests).
export function goToLogin(): void {
  window.location.assign("/api/auth/login");
}
