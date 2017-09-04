---
layout: default
title: Articles
permalink: /articles/
banner: https://farm1.staticflickr.com/22/25813836_15469bf8a4_o_d.jpg
---

<ul>
  {% for post in site.posts %}
    <li>
      <a href="{{ post.url }}">{{ post.title }}</a>
    </li>
  {% endfor %}
</ul>
