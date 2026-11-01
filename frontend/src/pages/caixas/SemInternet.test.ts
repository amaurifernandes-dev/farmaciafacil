import { describe, expect, it } from "vitest";

import { atraso } from "./SemInternet";

describe("atraso da venda feita sem internet", () => {
  it("mostra em minutos, horas ou dias", () => {
    expect(atraso("2026-11-01T10:00:00Z", "2026-11-01T10:25:00Z")).toBe("25 min");
    expect(atraso("2026-11-01T10:00:00Z", "2026-11-01T13:00:00Z")).toBe("3 h");
    expect(atraso("2026-11-01T10:00:00Z", "2026-11-01T13:15:00Z")).toBe("3 h 15 min");
    expect(atraso("2026-11-01T10:00:00Z", "2026-11-04T10:00:00Z")).toBe("3 dias");
    expect(atraso("2026-11-01T10:00:00Z", "2026-11-01T09:59:00Z")).toBe("0 min");
  });
});
