import { useEffect, useState } from "react";
import { resolveResultLink, ResultLinkInfo } from "../api/client";
import { ResultLinkContext } from "../components/ResultLinkContext";
import { CandidateResultPage } from "./CandidateResultPage";

export function ResultLinkPage({ token }: { token: string }) {
  const [linkToken] = useState(() => window.location.hash.slice(1));
  const [link, setLink] = useState<ResultLinkInfo | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    if (!linkToken) { setError(true); return; }
    resolveResultLink(token, linkToken, controller.signal).then((data) => {
      if (!controller.signal.aborted) setLink(data);
    }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [token, linkToken]);
  if (error) return <main><h1>Ссылка недоступна</h1><p role="alert">Ссылка отозвана, срок её действия истёк или нет связи с сервером. Обратитесь к рекрутеру или повторите открытие.</p></main>;
  if (!link) return <p role="status">Проверяем ссылку…</p>;
  return <ResultLinkContext.Provider value={linkToken}><CandidateResultPage token={token} candidateId={link.candidate_id} shared /></ResultLinkContext.Provider>;
}
