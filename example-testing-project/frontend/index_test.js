const add = require('./index');

test('adds 1 + 2 to equal 3', () => {
  expect(add(1, 2)).toBe(3);
});

test('adds -1 + -1 to equal -2', () => {
  expect(add(-1, -1)).toBe(-2);
});

test('adds 0 + 0 to equal 0', () => {
  expect(add(0, 0)).toBe(0);
});

test('adds 1.5 + 2.3 to equal 3.8', () => {
  expect(add(1.5, 2.3)).toBeCloseTo(3.8);
});