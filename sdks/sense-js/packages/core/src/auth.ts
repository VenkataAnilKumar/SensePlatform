/**
 * Sense Platform — Auth Manager
 * Handles JWT token storage, refresh, and injection into requests.
 */

import type { SenseUser, TokenResponse } from "./types.js";

export class SenseAuth {
  private _token: string | null = null;
  private _expiresAt: number = 0;
  private _user: SenseUser | null = null;

  constructor(private readonly gateUrl: string, private apiKey?: string) {}

  /**
   * Authenticate as a user and obtain a JWT from Sense Gate.
   * Call this once on session start — token is cached automatically.
   */
  async login(userId: string, userName?: string, role = "user"): Promise<string> {
    if (!this.apiKey) {
      throw new Error("@sense/core: apiKey is required to call auth.login()");
    }

    const resp = await fetch(`${this.gateUrl}/auth/token`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": this.apiKey,
      },
      body: JSON.stringify({ user_id: userId, user_name: userName ?? userId, role }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(`Auth failed: ${err.detail ?? resp.statusText}`);
    }

    const data: TokenResponse = await resp.json();
    this._token = data.accessToken ?? (data as unknown as { access_token: string }).access_token;
    this._expiresAt = Date.now() + (data.expiresIn ?? (data as unknown as { expires_in: number }).expires_in) * 1000;
    this._user = { id: userId, name: userName, role };
    return this._token;
  }

  /** Set a token directly (e.g. token issued server-side). */
  setToken(token: string, expiresInSeconds = 86400): void {
    this._token = token;
    this._expiresAt = Date.now() + expiresInSeconds * 1000;
  }

  getToken(): string | null {
    return this._token;
  }

  getUser(): SenseUser | null {
    return this._user;
  }

  isAuthenticated(): boolean {
    return !!this._token && Date.now() < this._expiresAt;
  }

  /** Return Authorization header value or throw if not authenticated. */
  authHeader(): string {
    if (!this._token) throw new Error("@sense/core: not authenticated. Call auth.login() first.");
    return `Bearer ${this._token}`;
  }

  logout(): void {
    this._token = null;
    this._expiresAt = 0;
    this._user = null;
  }
}
