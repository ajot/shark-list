// Rate limit handling
let rateLimitInterval = null;

function updateRateLimitUI() {
    const resetTimestamp = localStorage.getItem('rate_limit_reset');
    const banner = document.getElementById('rate-limit-banner');
    const countdown = document.getElementById('rate-limit-countdown');

    console.log('updateRateLimitUI called', { resetTimestamp, hasBanner: !!banner, hasCountdown: !!countdown });

    if (!resetTimestamp) {
        if (banner) banner.style.display = 'none';
        enableAllButtons();
        if (rateLimitInterval) {
            clearInterval(rateLimitInterval);
            rateLimitInterval = null;
        }
        return;
    }

    const resetTime = parseInt(resetTimestamp);
    const now = Math.floor(Date.now() / 1000);
    const secondsRemaining = resetTime - now;

    console.log('Rate limit active', { resetTime, now, secondsRemaining });

    if (secondsRemaining <= 0) {
        // Rate limit expired
        console.log('Rate limit expired, reloading page');
        localStorage.removeItem('rate_limit_reset');
        if (banner) banner.style.display = 'none';
        enableAllButtons();
        if (rateLimitInterval) {
            clearInterval(rateLimitInterval);
            rateLimitInterval = null;
        }
        // Reload page to clear session
        window.location.reload();
        return;
    }

    // Show banner and update countdown
    console.log('Showing banner and updating countdown');
    if (banner) {
        banner.style.display = 'block';
        console.log('Banner display set to block');
    }
    if (countdown) {
        const minutes = Math.floor(secondsRemaining / 60);
        const seconds = secondsRemaining % 60;
        countdown.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        console.log('Countdown updated to:', countdown.textContent);
    }

    // Disable all buttons
    disableAllButtons();
}

function disableAllButtons() {
    const buttons = document.querySelectorAll('[id^="approve-"], [id^="reject-"]');
    buttons.forEach(button => {
        button.disabled = true;
        button.style.opacity = '0.5';
        button.style.cursor = 'not-allowed';
    });
}

function enableAllButtons() {
    const buttons = document.querySelectorAll('[id^="approve-"], [id^="reject-"]');
    buttons.forEach(button => {
        button.disabled = false;
        button.style.opacity = '1';
        button.style.cursor = 'pointer';
    });
}

function handleRateLimitError(errorMessage) {
    console.log('handleRateLimitError called with:', errorMessage);

    // Check if error is rate limit related
    if (!errorMessage || !errorMessage.toLowerCase().includes('rate limit')) {
        console.log('Not a rate limit error');
        return false;
    }

    console.log('Rate limit error detected, attempting to parse timestamp');

    // Extract timestamp from error message
    const match = errorMessage.match(/Resets at (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/);
    if (match) {
        const dateStr = match[1];
        console.log('Parsed reset time:', dateStr);
        const resetDate = new Date(dateStr);
        const resetTimestamp = Math.floor(resetDate.getTime() / 1000);
        console.log('Reset timestamp:', resetTimestamp);

        localStorage.setItem('rate_limit_reset', resetTimestamp);
        updateRateLimitUI();

        // Start interval to update countdown
        if (!rateLimitInterval) {
            rateLimitInterval = setInterval(updateRateLimitUI, 1000);
        }
        return true;
    } else {
        console.log('Could not parse reset time from message');
    }
    return false;
}

// Initialize rate limit UI on page load
document.addEventListener('DOMContentLoaded', function() {
    // Check if rate limit is active (from template variable)
    if (typeof window.rateLimitActive !== 'undefined' && window.rateLimitActive) {
        if (typeof window.rateLimitReset !== 'undefined' && window.rateLimitReset) {
            localStorage.setItem('rate_limit_reset', window.rateLimitReset);
        }
    }

    updateRateLimitUI();

    // Start interval to update countdown
    if (localStorage.getItem('rate_limit_reset')) {
        rateLimitInterval = setInterval(updateRateLimitUI, 1000);
    }
});

// Toast notification system
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toast-message');

    if (!toast || !toastMessage) return;

    // Set border color based on type
    const borderColors = {
        'success': 'border-green-500',
        'error': 'border-red-500',
        'info': 'border-blue-500'
    };

    // Remove old border colors
    toast.classList.remove('border-green-500', 'border-red-500', 'border-blue-500');
    // Add new border color
    toast.classList.add(borderColors[type] || 'border-blue-500');

    toastMessage.textContent = message;
    toast.classList.remove('hidden');

    // Auto hide after 5 seconds
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 5000);
}

// Approve a single submission
function approveSubmission(submissionId) {
    const button = document.getElementById(`approve-${submissionId}`);
    if (button) {
        button.disabled = true;
        button.textContent = 'Processing...';
    }

    fetch(`/admin/approve/${submissionId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            // Remove the row after a short delay
            setTimeout(() => {
                const row = document.getElementById(`row-${submissionId}`);
                if (row) {
                    row.style.opacity = '0';
                    row.style.transition = 'opacity 0.3s';
                    setTimeout(() => row.remove(), 300);
                }
            }, 1000);
        } else {
            // Check if this is a rate limit error
            const isRateLimit = handleRateLimitError(data.message);

            showToast(data.message, 'error');
            if (button && !isRateLimit) {
                button.disabled = false;
                button.textContent = 'Approve';
            }
        }
    })
    .catch(error => {
        showToast('Network error: ' + error.message, 'error');
        if (button) {
            button.disabled = false;
            button.textContent = 'Approve';
        }
    });
}

// Reject a single submission
function rejectSubmission(submissionId) {
    if (!confirm('Are you sure you want to reject this submission?')) {
        return;
    }

    const button = document.getElementById(`reject-${submissionId}`);
    if (button) {
        button.disabled = true;
        button.textContent = 'Processing...';
    }

    fetch(`/admin/reject/${submissionId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            // Remove the row after a short delay
            setTimeout(() => {
                const row = document.getElementById(`row-${submissionId}`);
                if (row) {
                    row.style.opacity = '0';
                    row.style.transition = 'opacity 0.3s';
                    setTimeout(() => row.remove(), 300);
                }
            }, 1000);
        } else {
            // Check if this is a rate limit error
            const isRateLimit = handleRateLimitError(data.message);

            showToast(data.message, 'error');
            if (button && !isRateLimit) {
                button.disabled = false;
                button.textContent = 'Reject';
            }
        }
    })
    .catch(error => {
        showToast('Network error: ' + error.message, 'error');
        if (button) {
            button.disabled = false;
            button.textContent = 'Reject';
        }
    });
}

// Remove a member from the list (for submissions)
function removeMember(submissionIdOrMemberId, isMember = false) {
    if (!confirm('Are you sure you want to remove this member from the Twitter list?')) {
        return;
    }

    const buttonId = isMember ? `remove-member-${submissionIdOrMemberId}` : `remove-${submissionIdOrMemberId}`;
    const rowId = isMember ? `member-row-${submissionIdOrMemberId}` : `row-${submissionIdOrMemberId}`;
    const endpoint = isMember ? `/admin/remove-member/${submissionIdOrMemberId}` : `/admin/remove/${submissionIdOrMemberId}`;

    const button = document.getElementById(buttonId);
    if (button) {
        button.disabled = true;
        button.textContent = 'Removing...';
    }

    fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast(data.message, 'success');
            // Remove the row after a short delay
            setTimeout(() => {
                const row = document.getElementById(rowId);
                if (row) {
                    row.style.opacity = '0';
                    row.style.transition = 'opacity 0.3s';
                    setTimeout(() => row.remove(), 300);
                }
            }, 1000);
        } else {
            showToast(data.message, 'error');
            if (button) {
                button.disabled = false;
                button.textContent = 'Remove';
            }
        }
    })
    .catch(error => {
        showToast('Network error: ' + error.message, 'error');
        if (button) {
            button.disabled = false;
            button.textContent = 'Remove';
        }
    });
}

// Sync Twitter list members
function syncList() {
    // Check if sync is allowed
    if (typeof canSync !== 'undefined' && !canSync) {
        showToast(syncMessage || 'Sync not allowed at this time', 'error');
        return;
    }

    if (!confirm('This will fetch all members from your Twitter list and update the database. Continue?')) {
        return;
    }

    const button = document.getElementById('sync-button');
    const loadingModal = document.getElementById('loading-modal');

    if (button) {
        button.disabled = true;
    }

    if (loadingModal) {
        loadingModal.classList.remove('hidden');
    }

    fetch('/admin/sync', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (loadingModal) {
            loadingModal.classList.add('hidden');
        }

        if (data.success) {
            showToast(data.message, 'success');
            // Reload page after 2 seconds to show updated data
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            showToast(data.message, 'error');
            if (button) {
                button.disabled = false;
            }
        }
    })
    .catch(error => {
        if (loadingModal) {
            loadingModal.classList.add('hidden');
        }
        showToast('Network error: ' + error.message, 'error');
        if (button) {
            button.disabled = false;
        }
    });
}

// Check rate limit status
function checkRateLimit() {
    const button = document.getElementById('check-rate-limit-btn');

    if (button) {
        button.disabled = true;
        button.textContent = 'Checking...';
    }

    fetch('/admin/check-rate-limit', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success && data.rate_limit_info) {
            const info = data.rate_limit_info;

            // Update the count display
            const countElement = document.getElementById('rate-limit-count');
            if (countElement) {
                countElement.textContent = `${info.remaining} / ${info.limit}`;

                // Update color based on remaining requests
                countElement.classList.remove('text-red-600', 'text-yellow-600', 'text-green-600', 'text-gray-400');
                if (info.remaining < 50) {
                    countElement.classList.add('text-red-600');
                } else if (info.remaining < 150) {
                    countElement.classList.add('text-yellow-600');
                } else {
                    countElement.classList.add('text-green-600');
                }
            }

            // Update the progress bar
            const barElement = document.getElementById('rate-limit-bar');
            if (barElement) {
                const percentage = Math.round((info.remaining / info.limit) * 100);
                barElement.style.width = `${percentage}%`;

                // Update bar color
                barElement.classList.remove('bg-red-600', 'bg-yellow-500', 'bg-green-600');
                if (info.remaining < 50) {
                    barElement.classList.add('bg-red-600');
                } else if (info.remaining < 150) {
                    barElement.classList.add('bg-yellow-500');
                } else {
                    barElement.classList.add('bg-green-600');
                }
            }

            // Update reset time if available
            if (info.reset) {
                const resetTimeElement = document.getElementById('reset-time');
                if (resetTimeElement) {
                    resetTimeElement.setAttribute('data-reset', info.reset);
                }
            }

            showToast(data.message, 'success');
        } else {
            showToast(data.message || 'Failed to check rate limit', 'error');
        }

        if (button) {
            button.disabled = false;
            button.textContent = '🔄 Check Now';
        }
    })
    .catch(error => {
        showToast('Network error: ' + error.message, 'error');
        if (button) {
            button.disabled = false;
            button.textContent = '🔄 Check Now';
        }
    });
}

// Bulk mode management
let bulkModeEnabled = false;

function toggleBulkMode() {
    bulkModeEnabled = !bulkModeEnabled;
    const checkboxes = document.querySelectorAll('.bulk-checkbox');
    const bulkModeBtn = document.getElementById('bulkModeBtn');
    const bulkApproveBtn = document.getElementById('bulkApproveBtn');

    checkboxes.forEach(checkbox => {
        if (bulkModeEnabled) {
            checkbox.classList.remove('hidden');
        } else {
            checkbox.classList.add('hidden');
            checkbox.checked = false;
        }
    });

    if (bulkModeBtn) {
        bulkModeBtn.textContent = bulkModeEnabled ? 'Disable Bulk Mode' : 'Enable Bulk Mode';
    }

    if (bulkApproveBtn) {
        if (bulkModeEnabled) {
            bulkApproveBtn.classList.remove('hidden');
        } else {
            bulkApproveBtn.classList.add('hidden');
        }
    }
}

function toggleSelectAll(checkbox) {
    const submissionCheckboxes = document.querySelectorAll('.submission-checkbox');
    submissionCheckboxes.forEach(cb => {
        cb.checked = checkbox.checked;
    });
}

function bulkApprove() {
    const checkedBoxes = document.querySelectorAll('.submission-checkbox:checked');
    const submissionIds = Array.from(checkedBoxes).map(cb => parseInt(cb.value));

    if (submissionIds.length === 0) {
        showToast('Please select at least one submission', 'error');
        return;
    }

    if (!confirm(`Are you sure you want to approve ${submissionIds.length} submissions?`)) {
        return;
    }

    const bulkApproveBtn = document.getElementById('bulkApproveBtn');
    if (bulkApproveBtn) {
        bulkApproveBtn.disabled = true;
        bulkApproveBtn.textContent = 'Processing...';
    }

    fetch('/admin/bulk-approve', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            submission_ids: submissionIds
        })
    })
    .then(response => response.json())
    .then(data => {
        // Check for rate limit errors in the message or failed results
        let hasRateLimit = false;
        if (data.message && handleRateLimitError(data.message)) {
            hasRateLimit = true;
        }

        // Check failed results for rate limit errors
        if (data.results && data.results.failed.length > 0) {
            data.results.failed.forEach(item => {
                if (item.error && handleRateLimitError(item.error)) {
                    hasRateLimit = true;
                }
            });
        }

        showToast(data.message, data.success ? 'success' : 'error');

        // Show detailed results if there were failures
        if (data.results && data.results.failed.length > 0) {
            console.log('Failed approvals:', data.results.failed);
        }

        // Remove successful rows after a short delay
        if (data.results && data.results.success.length > 0) {
            setTimeout(() => {
                data.results.success.forEach(item => {
                    const row = document.getElementById(`row-${item.id}`);
                    if (row) {
                        row.style.opacity = '0';
                        row.style.transition = 'opacity 0.3s';
                        setTimeout(() => row.remove(), 300);
                    }
                });
            }, 1500);
        }

        if (bulkApproveBtn && !hasRateLimit) {
            bulkApproveBtn.disabled = false;
            bulkApproveBtn.textContent = 'Approve Selected';
        }

        // Reset bulk mode after processing (if not rate limited)
        if (!hasRateLimit) {
            setTimeout(() => {
                if (bulkModeEnabled) {
                    toggleBulkMode();
                }
            }, 2000);
        }
    })
    .catch(error => {
        showToast('Network error: ' + error.message, 'error');
        if (bulkApproveBtn) {
            bulkApproveBtn.disabled = false;
            bulkApproveBtn.textContent = 'Approve Selected';
        }
    });
}
