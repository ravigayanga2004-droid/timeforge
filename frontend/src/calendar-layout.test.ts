import { expect, it } from "vitest";
import type { Assignment } from "./api";
import { calendarLanes } from "./calendar-layout";
function a(id: number, start: number, end: number): Assignment {
  return {
    section_id: id,
    session_number: 1,
    day: 0,
    start,
    end,
    room_id: id,
    lecturer_id: id,
    is_locked: false,
    notes: "",
  };
}
it("keeps overlapping independent classes visible and reuses lanes after an interval ends", () => {
  const result = calendarLanes([
    a(1, 540, 600),
    a(2, 570, 660),
    a(3, 600, 630),
    a(4, 700, 760),
  ]);
  expect(result["1:1"].count).toBe(2);
  expect(result["2:1"].lane).not.toBe(result["1:1"].lane);
  expect(result["3:1"].lane).toBe(result["1:1"].lane);
  expect(result["4:1"]).toEqual({ lane: 0, count: 1 });
});
