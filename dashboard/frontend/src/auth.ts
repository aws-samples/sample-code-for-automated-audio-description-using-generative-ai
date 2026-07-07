/**
 * Lightweight Cognito authentication using the amazon-cognito-identity-js SDK.
 * Loads configuration from /auth-config.json deployed by CDK at deploy time.
 */
import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserSession,
} from "amazon-cognito-identity-js";

interface AuthConfig {
  userPoolId: string;
  userPoolClientId: string;
  region: string;
}

let userPool: CognitoUserPool | null = null;
let authConfig: AuthConfig | null = null;

export async function loadAuthConfig(): Promise<AuthConfig> {
  if (authConfig) return authConfig;

  const res = await fetch("/auth-config.json");
  if (!res.ok) {
    throw new Error("Failed to load auth configuration");
  }
  authConfig = await res.json();
  return authConfig!;
}

export async function getUserPool(): Promise<CognitoUserPool> {
  if (userPool) return userPool;

  const config = await loadAuthConfig();
  userPool = new CognitoUserPool({
    UserPoolId: config.userPoolId,
    ClientId: config.userPoolClientId,
  });
  return userPool;
}

export async function signIn(
  email: string,
  password: string,
): Promise<CognitoUserSession> {
  const pool = await getUserPool();
  const user = new CognitoUser({ Username: email, Pool: pool });
  const authDetails = new AuthenticationDetails({
    Username: email,
    Password: password,
  });

  return new Promise((resolve, reject) => {
    user.authenticateUser(authDetails, {
      onSuccess: (session) => resolve(session),
      onFailure: (err) => reject(err),
      newPasswordRequired: (_userAttributes, requiredAttributes) => {
        // For the initial admin-created user, they need to set a new password.
        // We'll reject with a special error that the UI can handle.
        reject({
          code: "NewPasswordRequired",
          message: "New password required",
          user,
          requiredAttributes,
        });
      },
    });
  });
}

export async function completeNewPassword(
  user: CognitoUser,
  newPassword: string,
): Promise<CognitoUserSession> {
  return new Promise((resolve, reject) => {
    user.completeNewPasswordChallenge(newPassword, {}, {
      onSuccess: (session) => resolve(session),
      onFailure: (err) => reject(err),
    });
  });
}

export async function signOut(): Promise<void> {
  const pool = await getUserPool();
  const user = pool.getCurrentUser();
  if (user) {
    user.signOut();
  }
}

export async function getSession(): Promise<CognitoUserSession | null> {
  const pool = await getUserPool();
  const user = pool.getCurrentUser();
  if (!user) return null;

  return new Promise((resolve) => {
    user.getSession(
      (err: Error | null, session: CognitoUserSession | null) => {
        if (err || !session || !session.isValid()) {
          resolve(null);
        } else {
          resolve(session);
        }
      },
    );
  });
}

export async function getIdToken(): Promise<string | null> {
  const session = await getSession();
  if (!session) return null;
  return session.getIdToken().getJwtToken();
}
