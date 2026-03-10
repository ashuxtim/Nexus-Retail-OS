function assertPositiveNumber(value, fieldName) {
    const num = Number(value);
    if (isNaN(num) || num <= 0) {
        throw new Error(`Validation failed: '${fieldName}' must be a positive number. Got: ${value}`);
    }
    return num;
}

function assertNonNegativeNumber(value, fieldName) {
    const num = Number(value);
    if (isNaN(num) || num < 0) {
        throw new Error(`Validation failed: '${fieldName}' must be zero or positive. Got: ${value}`);
    }
    return num;
}

function assertString(value, fieldName, maxLength = 255) {
    if (typeof value !== 'string' || value.trim() === '') {
        throw new Error(`Validation failed: '${fieldName}' must be a non-empty string.`);
    }
    if (value.length > maxLength) {
        throw new Error(`Validation failed: '${fieldName}' exceeds max length of ${maxLength}.`);
    }
    return value.trim();
}

module.exports = { assertPositiveNumber, assertNonNegativeNumber, assertString };
