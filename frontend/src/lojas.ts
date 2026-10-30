import { useEffect, useState } from "react";

import { api } from "./api/cliente";
import type { Loja } from "./api/tipos";

/** Lojas ativas da farmácia, a matriz primeiro. */
export function useLojas(): Loja[] {
  const [lojas, setLojas] = useState<Loja[]>([]);
  useEffect(() => {
    api<Loja[]>("/lojas")
      .then((todas) => setLojas(todas.filter((l) => l.ativo)))
      .catch(() => setLojas([]));
  }, []);
  return lojas;
}
