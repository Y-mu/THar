import type { Metadata } from "next";

import { ChatPage } from "./components/ChatPage";

export const metadata: Metadata = {
  title: "对话 · THar",
  description: "与 THar 意图优先 Agent 对话",
};

export default function Page() {
  return <ChatPage />;
}
