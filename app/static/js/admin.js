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
            showToast(data.message, 'error');
            if (button) {
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
            showToast(data.message, 'error');
            if (button) {
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

        if (bulkApproveBtn) {
            bulkApproveBtn.disabled = false;
            bulkApproveBtn.textContent = 'Approve Selected';
        }

        // Reset bulk mode after processing
        setTimeout(() => {
            if (bulkModeEnabled) {
                toggleBulkMode();
            }
        }, 2000);
    })
    .catch(error => {
        showToast('Network error: ' + error.message, 'error');
        if (bulkApproveBtn) {
            bulkApproveBtn.disabled = false;
            bulkApproveBtn.textContent = 'Approve Selected';
        }
    });
}
