import { beforeEach, describe, expect, test } from "bun:test";
import { useCoverageStore } from "./coverageStore.ts";

const cov = () => useCoverageStore.getState();

// 通常再生 (rAF tick ~16ms) を 0.02s 刻みで模擬する。
function play(from: number, to: number): void {
  let prev = from;
  for (let t = from + 0.02; t <= to + 1e-9; t += 0.02) {
    cov().mark(prev, t);
    prev = t;
  }
}

describe("coverageStore", () => {
  beforeEach(() => {
    cov().reset(10); // 10s → 100 バケット
  });

  test("通常再生は間を埋める", () => {
    play(0, 1);
    expect(cov().heardSpan(0, 1)).toBe(true);
    expect(cov().percentHeard()).toBeCloseTo(0.1, 1);
  });

  test("倍速再生 (連続tickだが1tickあたりの進みが大きい) も間を埋める", () => {
    // 1.5倍速の連続再生を模擬 (rAF tick毎に実時間の1.5倍だけ位置が進む)。
    let prev = 0;
    for (let t = 0.03; t <= 1 + 1e-9; t += 0.03) {
      cov().mark(prev, t);
      prev = t;
    }
    expect(cov().heardSpan(0, 1)).toBe(true);
  });

  test("シーク跨ぎ (gap>0.3) は間を埋めない", () => {
    cov().mark(0, 5); // 5s ジャンプ → 着地バケットのみ
    expect(cov().heardSpan(0, 1)).toBe(false);
    expect(cov().heardSpan(5, 5.05)).toBe(true);
  });

  test("heardSpan は全バケット再生済みのときだけ true", () => {
    play(0, 0.5);
    expect(cov().heardSpan(0, 0.5)).toBe(true);
    expect(cov().heardSpan(0, 2)).toBe(false);
  });
});
