export type LoginCredentials = {
  username: string;
  password: string;
};

export type LoginResponse = {
  user_id: number;
  username: string;
  identity_level: "user" | "admin";
  message: string;
};
