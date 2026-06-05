document.addEventListener('DOMContentLoaded', function() {
    const tocContainer = document.getElementById('toc-container');
    const content = document.querySelector('.content');
    const headings = content.querySelectorAll('h2, h3');
    
    // 确保每个标题都有ID
    headings.forEach((heading, index) => {
        if (!heading.id) {
            heading.id = 'section-' + index;
        }
    });
    
    // 生成目录
    headings.forEach(heading => {
        const level = parseInt(heading.tagName.substring(1)) - 2; // h2=0, h3=1
        const item = document.createElement('div');
        item.className = `toc-item level-${level}`;
        
        const link = document.createElement('a');
        link.href = '#' + heading.id;
        link.textContent = heading.textContent;
        
        // 添加点击事件平滑滚动
        link.addEventListener('click', function(e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
        
        item.appendChild(link);
        tocContainer.appendChild(item);
    });
    
    // 高亮当前可见的目录项
    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            const id = entry.target.id;
            if (entry.isIntersecting) {
                document.querySelectorAll('#toc-container a').forEach(link => {
                    link.classList.remove('active');
                    if (link.getAttribute('href') === '#' + id) {
                        link.classList.add('active');
                    }
                });
            }
        });
    }, { threshold: 0.5 });
    
    headings.forEach(heading => {
        observer.observe(heading);
    });
});