import { describe, expect, it } from "vitest";

import { candidateCode, candidateLabel } from "./candidateCode";

describe("candidateCode", () => {
  it("форматирует UUID в короткий читаемый код", () => {
    expect(candidateCode("a1b2c3d4-e5f6-7890-abcd-ef1234567890")).toBe("К-A1B2-C3D4");
  });

  it("для коротких id добавляет префикс", () => {
    expect(candidateCode("c1")).toBe("К-c1");
    expect(candidateCode("c-high")).toBe("К-c-high");
  });
});

describe("candidateLabel", () => {
  it("предпочитает имя, если оно задано", () => {
    expect(candidateLabel("c1", " Иван Петров ")).toBe("Иван Петров");
  });

  it("без имени показывает код", () => {
    expect(candidateLabel("c1", null)).toBe("К-c1");
    expect(candidateLabel("c1", "  ")).toBe("К-c1");
  });
});
