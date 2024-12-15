// ...existing code...

let currentPage = 1; // 添加此行以宣告 currentPage

const membersPerPage = 50;
let totalPages = 1; // 初始化總頁數
let loading = false; // 防止多次加載

// 新增函數以獲取 Discord 默認頭像 URL
function getDefaultAvatarUrl(userId) {
    const discriminator = parseInt(userId.slice(-1)) || 0;
    const defaultIndex = discriminator % 5;
    return `https://cdn.discordapp.com/embed/avatars/${defaultIndex}.png`;
}

// 移除分頁按鈕的事件監聽
// document.getElementById('prevPage').addEventListener('click', prevPage);
// document.getElementById('nextPage').addEventListener('click', nextPage);

// 添加滾動事件監聽器以實現無限滾動
window.addEventListener('scroll', () => {
    if (loading) return;
    
    if ((window.innerHeight + window.scrollY) >= document.body.offsetHeight - 100) {
        // 接近底部
        if (currentPage < totalPages) {
            loading = true;
            loadMembers(currentPage + 1).then(() => {
                loading = false;
            }).catch(() => {
                loading = false;
            });
        }
    }
});

// 更新 loadMembers 函數以支持追加成員
async function loadMembers(page = 1) {
    try {
        const response = await fetch(`/api/members?page=${page}&limit=${membersPerPage}`);
        if (!response.ok) {
            throw new Error('Failed to fetch members');
        }
        
        const data = await response.json();
        const grid = document.getElementById('membersGrid');
        
        const membersHTML = data.members.map(member => `
            <div class="member-card" onclick="showMemberDetails('${member.user.id}')">
                <div class="member-info">
                    <img src="${member.user.avatar ? `https://cdn.discordapp.com/avatars/${member.user.id}/${member.user.avatar}.png` : getDefaultAvatarUrl(member.user.id)}" 
                         class="member-avatar" 
                         onerror="this.src='https://cdn.discordapp.com/embed/avatars/0.png'"
                         alt="${member.user.username}">
                    <div>
                        <h3>${member.user.username}</h3>
                        <p class="member-status ${member.status}">${member.status || 'offline'}</p>
                    </div>
                </div>
            </div>
        `).join('');
        
        grid.insertAdjacentHTML('beforeend', membersHTML);

        // 更新分頁資訊
        currentPage = data.currentPage;
        totalPages = data.totalPages;

        // 移除設定不存在元素的代碼
        // document.getElementById('currentPage').textContent = data.currentPage;
        // document.getElementById('totalPages').textContent = data.totalPages;
        // document.getElementById('prevPage').disabled = data.currentPage <= 1;
        // document.getElementById('nextPage').disabled = data.currentPage >= data.totalPages;

    } catch (error) {
        console.error('Error loading members:', error);
        if (page === 1) {
            document.getElementById('membersGrid').innerHTML = '<p>載入成員時發生錯誤</p>';
        }
    }
}

// 確保在頁面載入時初始化
document.addEventListener('DOMContentLoaded', () => {
    loadMembers(currentPage);
});

// 修正 showMemberDetails 函數以使用 Discord 的默認頭像
async function showMemberDetails(memberId) {
    currentMemberId = memberId;
    try {
        const response = await fetch(`/api/members/${memberId}`);
        const member = await response.json();
        
        const modalContent = document.getElementById('modalContent');
        const avatarUrl = member.user.avatar 
            ? `https://cdn.discordapp.com/avatars/${member.user.id}/${member.user.avatar}.png` 
            : getDefaultAvatarUrl(member.user.id);
        modalContent.innerHTML = `
            <div class="member-details">
                <img src="${avatarUrl}" style="width: 100px; height: 100px; border-radius: 50%;">
                <h3>${member.user.username}</h3>
                <p>ID: ${member.user.id}</p>
                <p>加入時間: ${new Date(member.joined_at).toLocaleString()}</p>
                <p>狀態: ${member.status}</p>
                <p>活動: ${member.activity || '無'}</p>
                <div class="member-roles">
                    ${member.roles.map(role => 
                        `<span class="role-tag">${role}</span>`
                    ).join('')}
                </div>
            </div>
        `;
        
        // 更新按鈕的 data-member-id
        document.querySelector('.mute-button').setAttribute('data-member-id', memberId);
        document.querySelector('.kick-button').setAttribute('data-member-id', memberId);
        document.querySelector('.block-button').setAttribute('data-member-id', memberId);
        
        document.getElementById('memberModal').style.display = 'block';
    } catch (error) {
        console.error('Error loading member details:', error);
    }
}

function closeModal() {
    document.getElementById('memberModal').style.display = 'none';
}

function refreshMembers() {
    loadMembers(currentPage);
}

// Define the functions in the global scope
async function kickMember(memberId) {
    try {
        const response = await fetch(`/api/admin/members/${memberId}/kick`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        const result = await response.json();
        if (result.success) {
            alert('成員已被踢出');
            closeModal();
            loadMembers(currentPage);
        } else {
            alert('踢出失敗: ' + result.error);
        }
    } catch (error) {
        console.error('Error kicking member:', error);
        alert('操作失敗');
    }
}

async function blockMember(memberId) {
    try {
        const response = await fetch(`/api/admin/members/${memberId}/block`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        const result = await response.json();
        if (result.success) {
            alert('成員已被封鎖');
            closeModal();
            loadMembers(currentPage);
        } else {
            alert('封鎖失敗: ' + result.error);
        }
    } catch (error) {
        console.error('Error blocking member:', error);
        alert('操作失敗');
    }
}

async function timeoutMember(memberId) {
    const duration = prompt('請輸入禁言時間（分鐘）:', '10');
    if (!duration) return;

    try {
        const response = await fetch(`/api/admin/members/${memberId}/timeout`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ duration: parseInt(duration) })
        });
        const result = await response.json();
        if (result.success) {
            alert('成員已被禁言');
            closeModal();
            loadMembers(currentPage);
        } else {
            alert('禁言失敗: ' + result.error);
        }
    } catch (error) {
        console.error('Error timing out member:', error);
        alert('操作失敗');
    }
}

// 保留其他現有的函數和事件監聽器
document.addEventListener('click', function(event) {
    if (event.target.classList.contains('kick-button')) {
        const memberId = event.target.getAttribute('data-member-id');
        kickMember(memberId);
    } else if (event.target.classList.contains('block-button')) {
        const memberId = event.target.getAttribute('data-member-id');
        blockMember(memberId);
    } else if (event.target.classList.contains('mute-button')) {
        const memberId = event.target.getAttribute('data-member-id');
        timeoutMember(memberId);
    }
});
