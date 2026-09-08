let notificationTimeout;
let pendingUsername = null;
let pendingButton = null;
let pendingPostLink = null;

function slideDown(el) {
    if (!el) return;
    if (el._animating) return;
    el._animating = true;
    
    el.classList.remove("collapsed");
    el.style.setProperty("display", "block", "important");
    el.style.overflow = "hidden";
    el.style.height = "0px";
    el.style.opacity = "0";
    el.style.paddingTop = "0px";
    el.style.paddingBottom = "0px";
    el.style.boxSizing = "border-box";
    
    const targetHeight = el.scrollHeight + 36;
    
    requestAnimationFrame(() => {
        el.style.transition = "height 0.32s cubic-bezier(0.25, 1, 0.5, 1), opacity 0.28s ease, padding 0.32s cubic-bezier(0.25, 1, 0.5, 1)";
        el.style.height = targetHeight + "px";
        el.style.opacity = "1";
        el.style.paddingTop = "16px";
        el.style.paddingBottom = "20px";
        
        setTimeout(() => {
            el.style.height = "auto";
            el.style.overflow = "";
            el.style.transition = "";
            el.style.paddingTop = "";
            el.style.paddingBottom = "";
            el._animating = false;
        }, 340);
    });
}

function slideUp(el) {
    if (!el) return;
    if (el._animating) return;
    el._animating = true;
    
    const currentHeight = el.scrollHeight + 36;
    el.style.boxSizing = "border-box";
    el.style.height = currentHeight + "px";
    el.style.opacity = "1";
    el.style.overflow = "hidden";
    el.style.paddingTop = "16px";
    el.style.paddingBottom = "20px";
    
    void el.offsetHeight; // Force reflow
    
    requestAnimationFrame(() => {
        el.style.transition = "height 0.3s cubic-bezier(0.25, 1, 0.5, 1), opacity 0.25s ease, padding 0.3s cubic-bezier(0.25, 1, 0.5, 1)";
        el.style.height = "0px";
        el.style.opacity = "0";
        el.style.paddingTop = "0px";
        el.style.paddingBottom = "0px";
        
        setTimeout(() => {
            el.classList.add("collapsed");
            el.style.display = "";
            el.style.height = "";
            el.style.opacity = "";
            el.style.paddingTop = "";
            el.style.paddingBottom = "";
            el.style.overflow = "";
            el.style.transition = "";
            el._animating = false;
        }, 320);
    });
}

function updateEksiklerCount(index) {
    const list = document.getElementById(`eksiklerListesi-${index}`);
    const badge = document.getElementById(`elemanSayisi-${index}`);
    if (!list || !badge) return;
    const items = Array.from(list.getElementsByTagName("li"));
    const visibleCount = items.filter((item) => item.style.display !== "none").length;
    badge.innerText = `Eksik: ${visibleCount}`;
}

function showNotification(message) {
    const notification = document.getElementById("notification");
    document.getElementById("notification-message").innerText = message;

    if (notification.classList.contains("visible")) {
        clearTimeout(notificationTimeout);
        notification.classList.remove("visible");
    }

    notification.style.display = "block";
    setTimeout(() => {
        notification.classList.add("visible");
    }, 10);

    notificationTimeout = setTimeout(() => {
        notification.classList.remove("visible");
    }, 3000);
}

let selectedExemptionDays = 0;

function selectExemptionDuration(days, buttonEl) {
    document.querySelectorAll(".duration-pill").forEach(btn => btn.classList.remove("active"));
    if (buttonEl) buttonEl.classList.add("active");

    const customBox = document.getElementById("customDurationBox");
    const summaryText = document.getElementById("exemptionSummaryText");
    const customInput = document.getElementById("customDaysInput");

    if (days === "custom") {
        if (customBox) customBox.style.display = "block";
        if (customInput) {
            customInput.focus();
            const val = parseInt(customInput.value, 10) || 1;
            selectedExemptionDays = val;
            if (summaryText) {
                summaryText.innerHTML = `Bu üye <strong>${val} gün boyunca</strong> tüm kontrollerde otomatik muaf tutulacaktır.`;
            }
        }
    } else {
        if (customBox) customBox.style.display = "none";
        selectedExemptionDays = parseInt(days, 10) || 0;
        if (summaryText) {
            if (selectedExemptionDays === 0) {
                summaryText.innerHTML = `Bu üye <strong>sadece seçili gönderi</strong> için izinli sayılacaktır.`;
            } else if (selectedExemptionDays === 1) {
                summaryText.innerHTML = `Bu üye <strong>1 gün (24 saat) boyunca</strong> tüm kontrollerde otomatik muaf tutulacaktır.`;
            } else {
                summaryText.innerHTML = `Bu üye <strong>${selectedExemptionDays} gün boyunca</strong> tüm kontrollerde otomatik muaf tutulacaktır.`;
            }
        }
    }
}
window.selectExemptionDuration = selectExemptionDuration;

function updateCustomDaysNote(val) {
    const parsed = parseInt(val, 10);
    const summaryText = document.getElementById("exemptionSummaryText");
    if (!parsed || parsed < 1) {
        selectedExemptionDays = 1;
        if (summaryText) summaryText.innerHTML = `Lütfen geçerli bir gün sayısı girin (Örn: 3).`;
    } else {
        selectedExemptionDays = parsed;
        if (summaryText) {
            summaryText.innerHTML = `Bu üye <strong>${parsed} gün boyunca</strong> tüm kontrollerde otomatik muaf tutulacaktır.`;
        }
    }
}
window.updateCustomDaysNote = updateCustomDaysNote;

function closeModal() {
    const modal = document.getElementById("confirmModal");
    if (modal) modal.classList.remove("show");
    pendingUsername = null;
    pendingButton = null;
    pendingPostLink = null;
}
window.closeModal = closeModal;

function addExemption(username, postLink, button) {
    pendingUsername = username;
    pendingButton = button;
    pendingPostLink = postLink;
    
    // Reset selection to default (0 days / Sadece Bu Post)
    selectedExemptionDays = 0;
    const pills = document.querySelectorAll(".duration-pill");
    pills.forEach((p, idx) => {
        if (idx === 0) p.classList.add("active");
        else p.classList.remove("active");
    });
    
    const customBox = document.getElementById("customDurationBox");
    if (customBox) customBox.style.display = "none";
    const customInput = document.getElementById("customDaysInput");
    if (customInput) customInput.value = "";
    
    const summaryText = document.getElementById("exemptionSummaryText");
    if (summaryText) {
        summaryText.innerHTML = `Bu üye <strong>sadece seçili gönderi</strong> için izinli sayılacaktır.`;
    }

    const usernameEl = document.getElementById("modalUsername");
    if (usernameEl) usernameEl.textContent = `@${username}`;

    const modal = document.getElementById("confirmModal");
    if (modal) modal.classList.add("show");
}
window.addExemption = addExemption;

function confirmExemption() {
    if (!pendingUsername || !pendingButton || !pendingPostLink) {
        return;
    }

    const username = pendingUsername;
    const button = pendingButton;
    const postLink = pendingPostLink;
    const days = selectedExemptionDays;

    closeModal();

    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Kaydediliyor...';

    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';

    fetch("/add_exemption", {
        method: "POST",
        headers: { 
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken
        },
        body: JSON.stringify({ post_link: postLink, username: username, days: days }),
    })
        .then((response) => response.json())
        .then((data) => {
            if (data.success) {
                if (days > 0) {
                    // Multi-day exemption: Remove this user from ALL post lists and details on the entire page
                    const allUserItems = document.querySelectorAll(`li[data-username="${username}"]`);
                    const affectedListIndices = new Set();

                    allUserItems.forEach((item) => {
                        const parentList = item.closest("ul");
                        const listId = parentList && parentList.id;
                        const indexPart = listId ? listId.split("-").pop() : null;
                        const idx = indexPart ? parseInt(indexPart, 10) : null;
                        if (idx) affectedListIndices.add(idx);

                        item.style.transition = "all 0.3s ease";
                        item.style.opacity = "0";
                        item.style.transform = "translateX(20px)";
                        setTimeout(() => item.remove(), 300);
                    });

                    // Remove from detailed user report if present
                    const detailCard = document.getElementById(`missing-posts-${username}`);
                    if (detailCard) {
                        const outerCard = detailCard.closest(".user-detail-card");
                        if (outerCard) {
                            outerCard.style.transition = "all 0.3s ease";
                            outerCard.style.opacity = "0";
                            setTimeout(() => outerCard.remove(), 300);
                        }
                    }

                    setTimeout(() => {
                        affectedListIndices.forEach(idx => updateEksiklerCount(idx));
                        const dayMsg = days > 1 ? `${days} gün süreyle` : `1 gün süreyle`;
                        showNotification(`@${username} ${dayMsg} izinli listesine eklendi!`);
                    }, 350);
                } else {
                    // Single post exemption: Remove only from current post list
                    const listItem = button.closest("li");
                    const parentList = listItem && listItem.parentElement;
                    const listId = parentList && parentList.id;
                    const indexPart = listId ? listId.split("-").pop() : null;
                    const idx = indexPart ? parseInt(indexPart, 10) : null;

                    if (listItem) {
                        listItem.style.transition = "all 0.3s ease";
                        listItem.style.opacity = "0";
                        listItem.style.transform = "translateX(20px)";

                        setTimeout(() => {
                            listItem.remove();
                            if (idx) updateEksiklerCount(idx);
                            showNotification(`@${username} bu gönderi için izinli sayıldı!`);
                        }, 300);
                    }
                }
                return;
            }

            showNotification(`Hata: ${data.message}`);
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-check"></i>';
        })
        .catch(() => {
            showNotification("Bir hata oluştu!");
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-check"></i>';
        });
}
window.confirmExemption = confirmExemption;

function fallbackCopyToClipboard(text, count) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-9999px";
    textArea.style.top = "0";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();

    try {
        const successful = document.execCommand("copy");
        showNotification(successful ? `Liste kopyalandi! Toplam eksik sayisi: ${count}` : "Kopyalama basarisiz oldu!");
    } catch (_error) {
        showNotification("Kopyalama desteklenmiyor!");
    }

    document.body.removeChild(textArea);
}

function kopyalaListeyiFrom(listElementId, label) {
    const list = document.getElementById(listElementId);
    if (!list) return;
    const listItems = list.getElementsByTagName("li");
    let text = "";

    for (let i = 0; i < listItems.length; i += 1) {
        const username = listItems[i].getAttribute("data-username");
        if (username) {
            text += `@${username}`;
            if (i < listItems.length - 1) {
                text += "\n";
            }
        }
    }

    const count = listItems.length;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text)
            .then(() => showNotification(`Liste kopyalandi! Toplam ${label} sayisi: ${count}`))
            .catch(() => fallbackCopyToClipboard(text, count));
        return;
    }

    fallbackCopyToClipboard(text, count);
}

function copyEksiklerList(index) {
    kopyalaListeyiFrom(`eksiklerListesi-${index}`, "eksik");
}

function copyCompletedList() {
    kopyalaListeyiFrom("completedList", "tamamlamis kullanici");
}

function filterEksiklerList(index) {
    const list = document.getElementById(`eksiklerListesi-${index}`);
    if (!list) return;
    
    const card = list.closest('.link-card');
    if (!card) return;
    
    const inputEl = card.querySelector(".search-input");
    const input = inputEl ? inputEl.value.toLowerCase() : "";
    const listItems = list.getElementsByTagName("li");

    for (let i = 0; i < listItems.length; i += 1) {

        const item = listItems[i];
        const textValue = item.innerText.toLowerCase();
        item.style.display = textValue.includes(input) ? "" : "none";
    }

    updateEksiklerCount(index);
}

function filterCompletedList() {
    const input = document.getElementById("completedSearchInput").value.toLowerCase();
    const list = document.getElementById("completedList");
    if (!list) return;
    const listItems = list.getElementsByTagName("li");

    for (let i = 0; i < listItems.length; i += 1) {
        const item = listItems[i];
        const textValue = item.innerText.toLowerCase();
        item.style.display = textValue.includes(input) ? "" : "none";
    }
}

window.addExemption = addExemption;
window.closeModal = closeModal;
window.confirmExemption = confirmExemption;
window.copyEksiklerList = copyEksiklerList;
window.copyCompletedList = copyCompletedList;
window.filterEksiklerList = filterEksiklerList;
window.filterCompletedList = filterCompletedList;
window.toggleCompletedSection = toggleCompletedSection;
window.toggleEksiklerSection = toggleEksiklerSection;
window.toggleDetayliRapor = toggleDetayliRapor;
window.toggleUserMissingPosts = toggleUserMissingPosts;
window.copyLink = copyLink;
window.refreshResults = refreshResults;
window.copyUserMissingPosts = copyUserMissingPosts;
window.copyToClipboard = copyToClipboard;

function toggleCompletedSection() {
    const section = document.getElementById("completedSection");
    const icon = document.getElementById("completedSectionIcon");
    if (!section) return;
    if (section.classList.contains("collapsed")) {
        slideDown(section);
        if (icon) icon.style.transform = "rotate(180deg)";
    } else {
        slideUp(section);
        if (icon) icon.style.transform = "rotate(0deg)";
    }
}

function toggleEksiklerSection(index) {
    const section = document.getElementById(`eksiklerSection-${index}`);
    const icon = document.getElementById(`eksiklerIcon-${index}`);
    if (!section) return;
    if (section.classList.contains("collapsed")) {
        slideDown(section);
        if (icon) icon.style.transform = "rotate(180deg)";
    } else {
        slideUp(section);
        if (icon) icon.style.transform = "rotate(0deg)";
    }
}

function toggleDetayliRapor() {
    const body = document.getElementById("detayliRaporContent");
    const icon = document.getElementById("detayliRaporIcon");
    if (!body) return;
    if (body.classList.contains("collapsed")) {
        slideDown(body);
        if (icon) icon.style.transform = "rotate(180deg)";
    } else {
        slideUp(body);
        if (icon) icon.style.transform = "rotate(0deg)";
    }
}

function toggleUserMissingPosts(username, idx) {
    const body = document.getElementById("missing-posts-" + username);
    const icon = document.getElementById("user-icon-" + idx);
    if (!body) return;
    if (body.classList.contains("collapsed")) {
        slideDown(body);
        if (icon) icon.style.transform = "rotate(180deg)";
    } else {
        slideUp(body);
        if (icon) icon.style.transform = "rotate(0deg)";
    }
}

function copyLink(link) {
    navigator.clipboard.writeText(link).then(() => {
        showNotification("Link kopyalandi!");
    }).catch(() => {
        showNotification("Link kopyalanamadi!");
    });
}

function copyUserMissingPosts(username) {
    const container = document.getElementById('missing-posts-' + username);
    if (!container) return;
    
    const links = [];
    container.querySelectorAll('a').forEach(a => {
        links.push(a.textContent);
    });
    
    const text = links.join('\n');
    navigator.clipboard.writeText(text).then(() => {
        showNotification("@" + username + " için " + links.length + " link kopyalandı!");
    }).catch(() => {
        showNotification("Kopyalama başarısız!");
    });
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification("Kopyalandı!");
    }).catch(() => {
        showNotification("Kopyalama başarısız!");
    });
}

function refreshResults() {
    const links = [];
    document.querySelectorAll('.eksikler-list').forEach(list => {
        const postLink = list.dataset.postLink;
        if (postLink && !links.includes(postLink)) {
            links.push(postLink);
        }
    });
    
    const groupUsers = [];
    document.querySelectorAll('.eksikler-list li').forEach(item => {
        const username = item.dataset.username;
        if (username && !groupUsers.includes(username)) {
            groupUsers.push(username);
        }
    });
    
    const allCommented = [];
    document.querySelectorAll('#completedList li').forEach(item => {
        const username = item.dataset.username;
        if (username) {
            allCommented.push(username);
        }
    });
    
    const allUsers = [...groupUsers, ...allCommented];
    
    if (links.length > 0) {
        const linkParam = encodeURIComponent(links.join('\n'));
        const groupParam = encodeURIComponent(allUsers.join(' '));
        window.location.href = `/?refresh=1&link=${linkParam}&group=${groupParam}`;
    }
}

function showCommentModal(username) {
    const comments = (window.userComments && window.userComments[username.toLowerCase()]) || [];
    const usernameSpan = document.getElementById("commentModalUsername");
    const contentBlock = document.getElementById("commentModalContent");
    const warningBlock = document.getElementById("commentModalWarning");
    
    if (usernameSpan) usernameSpan.textContent = username;
    
    const isViolating = window.invalidCommentUsers && window.invalidCommentUsers.includes(username.toLowerCase());
    if (warningBlock) {
        warningBlock.style.display = isViolating ? "block" : "none";
    }
    
    if (contentBlock) {
        if (comments.length === 0) {
            contentBlock.textContent = "(Yorum içeriği bulunamadı)";
        } else if (comments.length === 1) {
            contentBlock.textContent = comments[0];
        } else {
            contentBlock.replaceChildren();
            comments.forEach((comment, index) => {
                const row = document.createElement("div");
                row.style.marginBottom = index === comments.length - 1 ? "0" : "10px";
                row.textContent = `${index + 1}. ${comment}`;
                contentBlock.appendChild(row);
            });
        }
    }
    
    const modal = document.getElementById("commentDetailModal");
    if (modal) {
        modal.classList.add("show");
    }
}

function closeCommentModal() {
    const modal = document.getElementById("commentDetailModal");
    if (modal) {
        modal.classList.remove("show");
    }
}

window.showCommentModal = showCommentModal;
window.closeCommentModal = closeCommentModal;

window.onload = function onLoad() {
    const lists = document.querySelectorAll(".eksikler-list");
    lists.forEach((list, idx) => {
        const indexPart = list.id.split("-").pop();
        const index = parseInt(indexPart, 10);
        if (index) updateEksiklerCount(index);
    });
    
    const completedList = document.getElementById("completedList");
    if (completedList) {
        completedList.addEventListener("click", (e) => {
            // Sürükleme kulbu (drag-handle) tıklandıysa modalı açma
            if (e.target.closest(".drag-handle-inner")) {
                return;
            }
            const li = e.target.closest("li.list-group-item");
            if (li) {
                const username = li.getAttribute("data-username");
                if (username) {
                    showCommentModal(username);
                }
            }
        });
        
        const items = completedList.querySelectorAll("li.list-group-item");
        items.forEach(item => {
            item.style.cursor = "pointer";
            item.title = "Kullanıcının yazdığı yorumu görmek için tıklayın";
        });
    }
    
    window.addEventListener("click", (e) => {
        const modal = document.getElementById("commentDetailModal");
        if (e.target === modal) {
            closeCommentModal();
        }
    });

    // Anlık Paylaşım Değiştirici
    if (window.resultThreadId) {
        const dropdownTextEl = document.getElementById("resultPostDropdownText");
        const optionsEl = document.getElementById("resultPostDropdownOptions");
        const containerEl = document.getElementById("resultPostSelectorContainer");
        
        if (dropdownTextEl && optionsEl && containerEl) {
            // Dün ve bugün atılan postları paralel çekelim
            Promise.all([
                fetch(`/api/get_group_posts/${window.resultThreadId}?date=yesterday`).then(r => r.json()),
                fetch(`/api/get_group_posts/${window.resultThreadId}?date=today`).then(r => r.json())
            ])
            .then(([resYest, resToday]) => {
                const postsYest = (resYest && resYest.posts) || [];
                const postsToday = (resToday && resToday.posts) || [];
                
                // Tekilleştirme
                const allPostsMap = new Map();
                postsToday.forEach(p => allPostsMap.set(p.url, p));
                postsYest.forEach(p => allPostsMap.set(p.url, p));
                
                const combinedPosts = Array.from(allPostsMap.values());
                
                if (combinedPosts.length > 0) {
                    optionsEl.innerHTML = "";
                    
                    combinedPosts.forEach(p => {
                        const div = document.createElement("div");
                        div.className = "dropdown-option d-flex align-items-center gap-2";
                        
                        const labelText = `@${p.username || 'Bilinmiyor'} (${p.date || 'Tarih Yok'})`;
                        const thumbHtml = p.thumbnail_url 
                            ? `<img src="${p.thumbnail_url}" class="post-dropdown-thumb" referrerpolicy="no-referrer" onerror="this.style.display='none';"><span class="icon">📷</span>`
                            : `<span class="icon">📷</span>`;
                            
                        div.innerHTML = `${thumbHtml} <span class="fw-semibold">@${p.username || 'Bilinmiyor'}</span> <span style="opacity: 0.6; font-size: 11px; margin-left: auto;">(${p.date || 'Tarih Yok'})</span>`;
                        div.setAttribute("data-value", p.url);
                        
                        const cleanPUrl = p.url ? p.url.trim().replace(/\/$/, "") : "";
                        const cleanCheckedUrl = window.checkedPostUrl ? window.checkedPostUrl.trim().replace(/\/$/, "") : "";
                        
                        if (cleanPUrl === cleanCheckedUrl) {
                            div.classList.add("selected");
                            if (p.thumbnail_url) {
                                dropdownTextEl.innerHTML = `<span class="d-inline-flex align-items-center gap-2"><img src="${p.thumbnail_url}" class="post-dropdown-thumb-sm" referrerpolicy="no-referrer"> <span>${labelText}</span></span>`;
                            } else {
                                dropdownTextEl.textContent = labelText;
                            }
                        }
                        
                        div.addEventListener("click", () => {
                            optionsEl.querySelectorAll(".dropdown-option").forEach(o => o.classList.remove("selected"));
                            div.classList.add("selected");
                            if (p.thumbnail_url) {
                                dropdownTextEl.innerHTML = `<span class="d-inline-flex align-items-center gap-2"><img src="${p.thumbnail_url}" class="post-dropdown-thumb-sm" referrerpolicy="no-referrer"> <span>${labelText}</span></span>`;
                            } else {
                                dropdownTextEl.textContent = labelText;
                            }
                            toggleResultDropdown('resultPostDropdown'); // close menu
                            
                            // ⚡ Seçim yapıldıktan sonra kartı otomatik gizle
                            const mainContainer = document.getElementById("resultPostSelectorContainer");
                            if (mainContainer) {
                                mainContainer.style.display = "none";
                            }
                            
                            changeCheckedPost(p.url);
                        });
                        
                        optionsEl.appendChild(div);
                    });
                    
                    // ⚡ Butona basılmadan önce kart kesinlikle gizli kalsın
                    containerEl.style.display = "none";
                    const btnWrapper = document.getElementById("togglePostSelectorBtnWrapper");
                    if (btnWrapper) btnWrapper.style.display = "block";
                } else {
                    containerEl.style.display = "none";
                }
            })
            .catch(err => {
                console.error("Grup paylaşımlarını yükleme hatası:", err);
                containerEl.style.display = "none";
            });
        }
    }
};

function toggleResultDropdown(id) {
    const dropdown = document.getElementById(id);
    if (!dropdown) return;
    const trigger = dropdown.querySelector('.dropdown-trigger');
    const menu = dropdown.querySelector('.dropdown-menu');
    if (!trigger || !menu) return;
    
    // Diğer açık dropdownları kapat
    document.querySelectorAll('.dropdown-menu').forEach(m => {
        if (m !== menu) m.classList.remove('show');
    });
    document.querySelectorAll('.dropdown-trigger').forEach(t => {
        if (t !== trigger) t.classList.remove('active');
    });
    
    trigger.classList.toggle('active');
    menu.classList.toggle('show');
}

function filterResultDropdown(dropdownId, value) {
    const dropdown = document.getElementById(dropdownId);
    if (!dropdown) return;
    const options = dropdown.querySelectorAll(".dropdown-option");
    const query = value.toLowerCase();
    
    options.forEach(opt => {
        const text = opt.textContent.toLowerCase();
        opt.style.display = text.includes(query) ? "" : "none";
    });
}

// Click outside helper
window.addEventListener("click", (e) => {
    if (!e.target.closest('.custom-dropdown')) {
        document.querySelectorAll('.dropdown-menu').forEach(m => m.classList.remove('show'));
        document.querySelectorAll('.dropdown-trigger').forEach(t => t.classList.remove('active'));
    }
});

function togglePostSelectorCard() {
    const mainContainer = document.getElementById("resultPostSelectorContainer");
    const container = document.getElementById("resultPostSelectorBody");
    const chevron = document.getElementById("postSelectorChevron");
    if (!mainContainer) return;
    
    const isHidden = mainContainer.style.display === "none" || mainContainer.style.display === "";
    if (isHidden) {
        mainContainer.style.display = "block";
        if (container) {
            slideDown(container);
            if (chevron) chevron.style.transform = "rotate(180deg)";
        }
        // Otomatik açılır menüyü aç
        setTimeout(() => {
            const dropdown = document.getElementById("resultPostDropdown");
            if (dropdown && !dropdown.querySelector('.dropdown-menu.show')) {
                toggleResultDropdown("resultPostDropdown");
            }
        }, 120);
    } else {
        if (container && !container.classList.contains("collapsed")) {
            slideUp(container);
            if (chevron) chevron.style.transform = "rotate(0deg)";
        }
        setTimeout(() => {
            mainContainer.style.display = "none";
        }, 200);
    }
}

window.toggleResultDropdown = toggleResultDropdown;
window.filterResultDropdown = filterResultDropdown;
window.togglePostSelectorCard = togglePostSelectorCard;

function changeCheckedPost(newUrl) {
    const todayStr = getIstanbulDateStr();
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    
    fetch("/api/save_selected_post", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken
        },
        body: JSON.stringify({
            thread_id: window.resultThreadId,
            date: todayStr,
            post_url: newUrl
        })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            // İlerleme overlay'ini göster
            const overlay = document.getElementById("progressOverlay");
            if (overlay) {
                overlay.style.display = "flex";
                void overlay.offsetHeight;
                overlay.classList.add("show");
            }
            
            // Gizli formu doldur ve gönder
            const refreshPostLink = document.getElementById("refreshPostLink");
            if (refreshPostLink) {
                refreshPostLink.value = newUrl;
            }
            
            const form = document.getElementById("resultRefreshForm");
            if (form) {
                form.submit();
            }
        } else {
            alert("Paylaşım seçimi kaydedilemedi.");
        }
    })
    .catch(err => {
        console.error("Paylaşım değiştirme hatası:", err);
        alert("Bağlantı hatası oluştu.");
    });
}

function getIstanbulDateStr() {
    const d = new Date();
    const formatter = new Intl.DateTimeFormat('en-CA', {
        timeZone: 'Europe/Istanbul',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
    });
    return formatter.format(d);
}

function showPostDetailsModal(index) {
    const data = window.postDetailsData ? window.postDetailsData[index] : null;
    if (!data) return;
    
    const ownerEl = document.getElementById("modalPostOwner");
    const fullnameEl = document.getElementById("modalPostOwnerFullname");
    const likesEl = document.getElementById("modalPostLikes");
    const commentsEl = document.getElementById("modalPostComments");
    const captionEl = document.getElementById("modalPostCaption");
    const linkBtn = document.getElementById("modalPostLinkBtn");
    const avatarImg = document.getElementById("modalPostAvatarImg");
    const avatarIcon = document.getElementById("modalPostAvatarIcon");
    
    const sender = data.sender ? data.sender.replace(/^@/, '') : '';
    if (ownerEl) ownerEl.textContent = sender ? "@" + sender : "Bilinmiyor";
    if (fullnameEl) fullnameEl.textContent = data.owner_fullname ? data.owner_fullname : "İsim Bilgisi Yok";
    if (likesEl) likesEl.textContent = Number(data.like_count).toLocaleString("tr-TR");
    if (commentsEl) commentsEl.textContent = Number(data.comment_count).toLocaleString("tr-TR");
    if (captionEl) captionEl.textContent = data.caption ? data.caption : "Açıklama bulunmuyor.";
    if (linkBtn) linkBtn.href = data.link;
    
    function setAvatar(picUrl) {
        if (!picUrl || !avatarImg) {
            if (avatarImg) avatarImg.style.display = "none";
            if (avatarIcon) avatarIcon.style.display = "block";
            return;
        }
        const proxiedUrl = `/api/proxy_image?url=${encodeURIComponent(picUrl)}`;
        avatarImg.src = proxiedUrl;
        avatarImg.style.display = "block";
        if (avatarIcon) avatarIcon.style.display = "none";
        avatarImg.onerror = function() {
            if (this.src.includes("/api/proxy_image")) {
                this.src = picUrl; // doğrudan dene
            } else {
                this.style.display = "none";
                if (avatarIcon) avatarIcon.style.display = "block";
            }
        };
    }

    const mediaWrap = document.getElementById("modalPostMediaWrap");
    const thumbImg = document.getElementById("modalPostThumbnailImg");
    const videoPlayer = document.getElementById("modalPostVideoPlayer");
    const playOverlay = document.getElementById("modalPostPlayOverlay");
    const badgeIcon = document.getElementById("modalPostMediaBadgeIcon");
    const badgeText = document.getElementById("modalPostMediaBadgeText");
    
    // Video durumunu sıfırla
    if (videoPlayer) {
        videoPlayer.pause();
        videoPlayer.src = "";
        videoPlayer.style.display = "none";
    }
    if (thumbImg) {
        thumbImg.style.display = "block";
    }
    if (playOverlay) {
        playOverlay.style.display = "none";
    }

    function setupMedia(isVid, vidUrl, thumbUrl) {
        if (!mediaWrap) return;
        
        if (!thumbUrl && !vidUrl) {
            mediaWrap.style.display = "none";
            return;
        }
        
        mediaWrap.style.display = "block";
        
        if (thumbUrl && thumbImg) {
            const proxiedThumb = `/api/proxy_image?url=${encodeURIComponent(thumbUrl)}`;
            thumbImg.src = proxiedThumb;
            thumbImg.onerror = function() {
                if (this.src.includes("/api/proxy_image")) {
                    this.src = thumbUrl;
                } else {
                    if (!isVid) mediaWrap.style.display = "none";
                }
            };
        }
        
        if (isVid && vidUrl) {
            if (badgeIcon) badgeIcon.className = "fas fa-film";
            if (badgeText) badgeText.textContent = "Reels Video";
            if (playOverlay) playOverlay.style.display = "flex";
            if (videoPlayer) {
                videoPlayer.src = `/api/proxy_image?url=${encodeURIComponent(vidUrl)}`;
                videoPlayer.onerror = function() {
                    if (this.src.includes("/api/proxy_image")) {
                        this.src = vidUrl;
                    }
                };
            }
        } else {
            if (badgeIcon) badgeIcon.className = "fas fa-camera";
            if (badgeText) badgeText.textContent = "Fotoğraf";
            if (playOverlay) playOverlay.style.display = "none";
        }
    }

    if (data.profile_pic_url) {
        setAvatar(data.profile_pic_url);
    } else if (sender) {
        if (avatarImg) avatarImg.style.display = "none";
        if (avatarIcon) avatarIcon.style.display = "block";
        fetch(`/api/user_avatar/${sender}`)
            .then(r => r.json())
            .then(res => {
                if (res.ok && res.profile_pic_url) {
                    data.profile_pic_url = res.profile_pic_url;
                    setAvatar(res.profile_pic_url);
                }
            })
            .catch(() => {});
    } else {
        if (avatarImg) avatarImg.style.display = "none";
        if (avatarIcon) avatarIcon.style.display = "block";
    }

    if (data.thumbnail_url || data.video_url) {
        setupMedia(data.is_video, data.video_url, data.thumbnail_url);
    } else if (data.link) {
        if (mediaWrap) mediaWrap.style.display = "none";
        fetch(`/api/get_post_thumbnail?link=${encodeURIComponent(data.link)}`)
            .then(r => r.json())
            .then(res => {
                if (res.ok) {
                    data.thumbnail_url = res.thumbnail_url || "";
                    data.is_video = res.is_video || false;
                    data.video_url = res.video_url || "";
                    setupMedia(data.is_video, data.video_url, data.thumbnail_url);
                    if (res.profile_pic_url && !data.profile_pic_url) {
                        data.profile_pic_url = res.profile_pic_url;
                        setAvatar(res.profile_pic_url);
                    }
                }
            })
            .catch(() => {});
    } else {
        if (mediaWrap) mediaWrap.style.display = "none";
    }
    
    window.currentActivePostIndex = index;
    
    const modal = document.getElementById("postDetailsModal");
    if (modal) {
        modal.classList.add("show");
    }
}

function playModalVideo() {
    const thumbImg = document.getElementById("modalPostThumbnailImg");
    const videoPlayer = document.getElementById("modalPostVideoPlayer");
    const playOverlay = document.getElementById("modalPostPlayOverlay");
    if (!videoPlayer) return;
    
    if (thumbImg) thumbImg.style.display = "none";
    if (playOverlay) playOverlay.style.display = "none";
    videoPlayer.style.display = "block";
    videoPlayer.play().catch(e => console.log("Video play error:", e));
}

function closePostDetailsModal() {
    const videoPlayer = document.getElementById("modalPostVideoPlayer");
    if (videoPlayer) {
        videoPlayer.pause();
        videoPlayer.currentTime = 0;
    }
    const modal = document.getElementById("postDetailsModal");
    if (modal) {
        modal.classList.remove("show");
    }
}

let currentInteractionsData = [];
let currentInteractionsType = 'comments';

function openInteractionsModal(type) {
    const data = window.postDetailsData && window.currentActivePostIndex ? window.postDetailsData[window.currentActivePostIndex] : null;
    if (!data) return;
    
    currentInteractionsType = type;
    const modal = document.getElementById("interactionsModal");
    const titleEl = document.getElementById("interactionsModalTitle");
    const iconEl = document.getElementById("interactionsModalIcon");
    const listContainer = document.getElementById("interactionsListContainer");
    const searchInput = document.getElementById("interactionsSearchInput");
    const badgeEl = document.getElementById("interactionsCountBadge");
    
    if (searchInput) searchInput.value = "";
    
    if (type === 'likes') {
        if (titleEl) titleEl.textContent = `Beğenenler (${data.like_count || 0})`;
        if (iconEl) iconEl.textContent = '❤️';
    } else {
        if (titleEl) titleEl.textContent = `Yorumlar (${data.comment_count || 0})`;
        if (iconEl) iconEl.textContent = '💬';
    }
    
    if (modal) modal.classList.add("show");
    
    function renderList(items) {
        currentInteractionsData = items;
        if (badgeEl) badgeEl.textContent = `${items.length} Kayıt`;
        if (!listContainer) return;
        
        if (!items || items.length === 0) {
            listContainer.innerHTML = `
                <div class="text-center py-4" style="color: var(--muted-foreground); font-size: 13.5px;">
                    <i class="fas fa-info-circle mb-2" style="font-size: 24px; color: var(--accent-caramel); display: block;"></i>
                    ${type === 'likes' ? 'Bu gönderi için henüz beğeni kaydı bulunamadı.' : 'Bu gönderide henüz yorum bulunamadı.'}
                </div>`;
            return;
        }
        
        let html = '';
        if (type === 'likes') {
            items.forEach((item) => {
                const uname = typeof item === 'string' ? item : (item.username || '');
                html += `
                    <div class="interaction-item d-flex align-items-center justify-content-between" data-search="${uname.toLowerCase()}" style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(196, 149, 106, 0.15); border-radius: 10px; padding: 10px 14px; margin-bottom: 8px; transition: all 0.2s ease;">
                        <div class="d-flex align-items-center gap-2">
                            <div style="width: 32px; height: 32px; border-radius: 50%; background: rgba(196, 149, 106, 0.15); display: flex; align-items: center; justify-content: center; border: 1px solid rgba(196, 149, 106, 0.3);">
                                <i class="fas fa-user text-accent-caramel" style="font-size: 14px; color: var(--accent-caramel);"></i>
                            </div>
                            <div>
                                <strong style="color: #fff; font-size: 13.5px;">@${uname}</strong>
                            </div>
                        </div>
                        <a href="https://instagram.com/${uname}" target="_blank" class="btn btn-sm" style="color: var(--accent-caramel); font-size: 11.5px; text-decoration: none;" title="Profili Aç">
                            <i class="fas fa-external-link-alt"></i>
                        </a>
                    </div>`;
            });
        } else {
            items.forEach((item) => {
                const uname = item.username || 'Kullanıcı';
                const text = item.text || '';
                html += `
                    <div class="interaction-item" data-search="${uname.toLowerCase()} ${text.toLowerCase()}" style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(196, 149, 106, 0.15); border-radius: 10px; padding: 10px 14px; margin-bottom: 8px; transition: all 0.2s ease;">
                        <div class="d-flex align-items-center justify-content-between mb-1">
                            <div class="d-flex align-items-center gap-2">
                                <div style="width: 28px; height: 28px; border-radius: 50%; background: rgba(196, 149, 106, 0.15); display: flex; align-items: center; justify-content: center; border: 1px solid rgba(196, 149, 106, 0.3);">
                                    <i class="fas fa-comment-dots" style="font-size: 12px; color: var(--accent-caramel);"></i>
                                </div>
                                <strong style="color: var(--accent-cream); font-size: 13px;">@${uname}</strong>
                            </div>
                            <a href="https://instagram.com/${uname}" target="_blank" style="color: var(--muted-foreground); font-size: 11px; text-decoration: none;" title="Profili Aç">
                                <i class="fas fa-external-link-alt"></i>
                            </a>
                        </div>
                        <div style="background: rgba(0, 0, 0, 0.3); border-radius: 8px; padding: 8px 12px; font-size: 12.5px; color: rgba(255, 255, 255, 0.9); line-height: 1.4; word-break: break-word; font-style: italic; border-left: 3px solid var(--accent-caramel);">
                            "${text}"
                        </div>
                    </div>`;
            });
        }
        listContainer.innerHTML = html;
    }
    
    // 1. Önce hafızadaki veriye bak
    if (type === 'comments' && data.comments_list && data.comments_list.length > 0) {
        renderList(data.comments_list);
        return;
    }
    if (type === 'likes' && data.likers_list && data.likers_list.length > 0) {
        renderList(data.likers_list);
        return;
    }
    
    // 2. Yoksa API'den sorgula
    if (listContainer) {
        listContainer.innerHTML = `
            <div class="text-center py-4" style="color: var(--accent-caramel); font-size: 13.5px;">
                <i class="fas fa-spinner fa-spin me-2"></i>Veriler Instagram'dan alınıyor...
            </div>`;
    }
    
    fetch(`/api/get_post_interactions?link=${encodeURIComponent(data.link)}&type=${type}`)
        .then(r => r.json())
        .then(res => {
            if (res.ok) {
                if (type === 'likes') {
                    data.likers_list = res.likers || [];
                    renderList(data.likers_list);
                } else {
                    data.comments_list = res.comments || [];
                    renderList(data.comments_list);
                }
            } else {
                if (listContainer) {
                    listContainer.innerHTML = `
                        <div class="text-center py-4" style="color: #f87171; font-size: 13px;">
                            <i class="fas fa-exclamation-triangle mb-2" style="font-size: 20px; display: block;"></i>
                            ${res.error || 'Veri yüklenemedi.'}
                        </div>`;
                }
            }
        })
        .catch(() => {
            if (listContainer) {
                listContainer.innerHTML = `<div class="text-center py-4" style="color: #f87171; font-size: 13px;">İletişim hatası oluştu.</div>`;
            }
        });
}

function closeInteractionsModal() {
    const modal = document.getElementById("interactionsModal");
    if (modal) modal.classList.remove("show");
}

function filterInteractionsList() {
    const query = (document.getElementById("interactionsSearchInput")?.value || "").toLowerCase().trim();
    const items = document.querySelectorAll("#interactionsListContainer .interaction-item");
    let count = 0;
    items.forEach(el => {
        const text = el.getAttribute("data-search") || "";
        if (!query || text.includes(query)) {
            el.style.display = "";
            count++;
        } else {
            el.style.display = "none";
        }
    });
    const badge = document.getElementById("interactionsCountBadge");
    if (badge) badge.textContent = `${count} Kayıt`;
}

function copyInteractionsList() {
    if (!currentInteractionsData || currentInteractionsData.length === 0) {
        alert("Kopyalanacak kayıt yok.");
        return;
    }
    let textToCopy = "";
    if (currentInteractionsType === 'likes') {
        textToCopy = currentInteractionsData.map(u => typeof u === 'string' ? u : (u.username || '')).join("\n");
    } else {
        textToCopy = currentInteractionsData.map(c => `@${c.username}: ${c.text}`).join("\n");
    }
    navigator.clipboard.writeText(textToCopy).then(() => {
        if (window.showNotification) {
            window.showNotification("Liste panoya kopyalandı!");
        } else {
            alert("Liste panoya kopyalandı!");
        }
    });
}

window.showPostDetailsModal = showPostDetailsModal;
window.closePostDetailsModal = closePostDetailsModal;
window.playModalVideo = playModalVideo;
window.openInteractionsModal = openInteractionsModal;
window.closeInteractionsModal = closeInteractionsModal;
window.filterInteractionsList = filterInteractionsList;
window.copyInteractionsList = copyInteractionsList;
